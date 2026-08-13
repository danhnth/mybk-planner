"""Planning analysis: turns fetched data into graduation-readiness insights.

Pure functions — no API calls, no imports from cli/repl. Inputs are the raw
payloads the fetchers already return (GPA rows, khối progress, grade records),
so this module stays unit-testable and the callers decide when to fetch.

VERIFIED shapes (live 2026-08):
  GPA feed rows (xem-ket-qua-hoc-tap/tinChiTichLuy):
    {"mahk": 20252, "tbtlchunghe4": "2.7", "tbtlchunghe10": "6.92", "tinchi": "105"}
    — cumulative per-semester, newest last. "BL"/"99991" rows are placeholders
    and are filtered out before trend math.
  Khối progress rows (CTĐT summary): {"khối": ..., "tc_required": 13.0,
    "tc_done": 9.0} — per-block credit requirements. The PLAN's own remaining
    credits (planner already re-adds retake credits) are the authority for
    "how much is left", and are passed in, not recomputed here.
"""

from __future__ import annotations

from typing import Any

NOT_A_SEMESTER = ("BL", "99991")


def _f(v: Any) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _real_semesters(gpa_rows: list[dict]) -> list[dict]:
    """Drop placeholder rows and keep the cumulative ones in order."""
    out = []
    for r in gpa_rows if isinstance(gpa_rows, list) else []:
        if not isinstance(r, dict):
            continue
        hk = str(r.get("mahk") or "").strip()
        if not hk or hk in NOT_A_SEMESTER:
            continue
        gpa10 = _f(r.get("tbtlchunghe10"))
        if gpa10 is None:
            continue
        out.append({
            "hk": hk,
            "gpa_4": _f(r.get("tbtlchunghe4")),
            "gpa_10": gpa10,
            "credits": _f(r.get("tinchi")),
        })
    return out


def gpa_trend(gpa_rows: list[dict]) -> dict:
    """Cumulative GPA trajectory + direction over the student's real semesters.

    Returns {direction, delta, recent_delta, current_gpa_10, current_gpa_4,
    semesters}. delta spans the whole transcript; recent_delta the last two
    semesters (a spike early on should not mask a current slide)."""
    sems = _real_semesters(gpa_rows)
    if not sems:
        return {"direction": "unknown", "delta": 0.0, "recent_delta": 0.0,
                "current_gpa_10": None, "current_gpa_4": None, "semesters": []}
    first, last = sems[0]["gpa_10"], sems[-1]["gpa_10"]
    delta = round(last - first, 2)
    recent = round(last - sems[-2]["gpa_10"], 2) if len(sems) > 1 else 0.0
    direction = "up" if delta > 0.05 else ("down" if delta < -0.05 else "flat")
    return {
        "direction": direction, "delta": delta, "recent_delta": recent,
        "current_gpa_10": last, "current_gpa_4": sems[-1]["gpa_4"],
        "semesters": sems,
    }


def completion(completed_credits: float, remaining_credits: float) -> dict:
    """Program completion from the plan's own numbers.

    total = completed + remaining (the CTĐT credit requirement the plan is
    graded against). percent is a plain ratio; no magic constants."""
    total = completed_credits + remaining_credits
    pct = round(100.0 * completed_credits / total, 1) if total else 100.0
    return {"completed": completed_credits, "remaining": remaining_credits,
            "total": total, "percent": pct}


def khoi_compliance(khoi_progress: list[dict]) -> list[dict]:
    """Per-block status: met / short-by credits, with the gap called out.

    A block is 'met' when tc_done >= tc_required. Short blocks are the
    planning surface — the UI highlights them; blocks that already meet are
    low priority even when courses inside them are optional."""
    out = []
    for k in khoi_progress if isinstance(khoi_progress, list) else []:
        if not isinstance(k, dict):
            continue
        req, done = _f(k.get("tc_required")) or 0.0, _f(k.get("tc_done")) or 0.0
        out.append({
            "khoi": k.get("khối") or "?",
            "required": req, "done": done,
            "gap": max(0.0, req - done),
            "met": done >= req,
        })
    return out


def grade_health(records: list) -> dict:
    """Transcript health from grade records: recovery load + letter buckets.

    Works at COURSE level, matching the transcript's pass authority: a code is
    "failed" only if its most recent record is not passed (a retake pass like
    MT1003 F@20231→D+@20233 clears the fail). Each failed course costs a slot
    that could be a new course; D-grades are improvable and raise GPA."""
    per_code: dict[str, dict] = {}
    for r in records:
        code = r.subject_code
        if not code:
            continue
        cur = per_code.get(code)
        if cur is None or (r.semester or "") >= (cur["semester"] or ""):
            per_code[code] = {
                "passed": r.passed, "letter": (r.letter or "").strip().upper(),
                "name": r.subject_name, "credits": r.credits,
                "score_10": r.score_10, "semester": r.semester,
            }
    failed: list[dict] = []
    d_courses: list[dict] = []
    letters: dict[str, int] = {}
    for code, rec in per_code.items():
        key = rec["letter"].replace("+", "") if rec["letter"] in ("A", "B", "C", "D", "D+", "F") else "other"
        letters[key] = letters.get(key, 0) + 1
        if not rec["passed"]:
            failed.append({"code": code, "name": rec["name"],
                           "credits": rec["credits"], "semester": rec["semester"]})
        elif rec["letter"] in ("D", "D+"):
            d_courses.append({"code": code, "name": rec["name"],
                              "credits": rec["credits"], "score_10": rec["score_10"],
                              "semester": rec["semester"]})
    return {"failed": failed, "d_courses": d_courses, "letters": letters}


def _tc_per_semester(gpa_rows: list[dict]) -> list[float]:
    """TC earned in each (cumulative) semester — the delta between consecutive
    cumulative totals. The feed's `tinchi` is cumulative, so averaging it
    directly would overstate pace; the incremental is the real load."""
    sems = _real_semesters(gpa_rows)
    out: list[float] = []
    prev = 0.0
    for s in sems:
        c = s["credits"]
        if c is not None:
            if c >= prev:
                out.append(round(c - prev, 1))
            prev = c
    return out


def timeline(remaining_credits: float, max_tc: float,
             gpa_rows: list[dict]) -> dict:
    """Estimated semesters left under two load scenarios.

    - at_max: remaining / max_tc (if you keep filling the cap)
    - at_pace: remaining / (average TC per real semester so far) — the
      student's actual demonstrated pace, which is usually lower than the cap.
    Returns {at_max, at_pace, avg_credits_per_sem}. Neither is a promise —
    they bracket how far away graduation is."""
    per_sem = [c for c in _tc_per_semester(gpa_rows) if c > 0]
    tc_avg = round(sum(per_sem) / len(per_sem), 1) if per_sem else 0.0

    def sems_needed(tc_per: float) -> int:
        if tc_per <= 0 or remaining_credits <= 0:
            return 0
        return int(-(-remaining_credits // tc_per))  # ceil

    return {
        "at_max": sems_needed(max_tc),
        "at_pace": sems_needed(tc_avg) if tc_avg else None,
        "avg_credits_per_sem": tc_avg or None,
    }


def next_semester_label(semesters: list[dict]) -> str:
    """Extrapolate the next HK code from the last known one (20252→20253; a
    YYYY3 rolls over to (YYYY+1)1). Falls back to a generic label."""
    if not semesters:
        return "HK tới"
    last_hk = str(semesters[-1].get("hk") or "")
    if len(last_hk) == 5 and last_hk[:4].isdigit():
        year, hk = int(last_hk[:4]), int(last_hk[4])
        return f"HK {year}{hk + 1}" if hk < 3 else f"HK {year + 1}1"
    return "HK tới"