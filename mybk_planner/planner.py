"""Recommendation engine: turns CTĐT + grades (+ open classes when a round is
live) into a prioritized next-semester course plan.

Data model (verified against the live CTĐT payload):

    CTĐT's `diemdat` means "has a grade record", NOT "passed" — failed courses
    still carry diemdat == "1". The pass authority is the GRADE LIST (diemDat
    in BANGDIEM_MONHOC rows). Courses with sotc > 0 whose code is not in the
    passed set are the REMAINING pool. douutien orders courses within each
    khối; tcyeucau/tcdat give per-khối credit progress. There is no per-course
    prerequisite field in the live payload — sequencing uses khối + douutien,
    and retakes (grades present but not passed) are prioritized ahead of new
    courses.

Open-class integration: reg_open_classes (sinh-vien/thoi-khoa-bieu/{HK}/RUTMON/v1)
is the WITHDRAWAL feed — it carries the round's class groups only while a đợt
is open. When data is present we annotate offered codes; off-season it stays
empty and the plan is purely CTĐT-driven (documented limitation).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import requests

from . import analysis
from .api import ApiError, MyBK
from .cas import CasError
from .fees import estimate as fee_estimate
from .models import CtdtCourse
from .open_classes import reg_open_classes
from .transcript import (
    ctdt_courses,
    get_student_info,
    grades,
    normalize_grade_rows,
    xem_ket_qua_hoc_tap,
)

DEFAULT_MAX_TC = 18  # 18 TC/HK is the HCMUT định mức (2026-27 fee notice §I.2.b); above it credits are billed separately


@dataclass
class PlanCourse:
    code: str
    name: str
    credits: float
    khoi: str
    douutien: float
    status: str  # "retake" | "new"
    offered: bool  # seen in the open-class feed this round
    groups: list = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "code": self.code, "name": self.name, "credits": self.credits,
            "khoi": self.khoi, "douutien": self.douutien, "status": self.status,
            "offered": self.offered, "groups": self.groups,
        }


@dataclass
class PlanResult:
    completed_credits: float
    remaining_credits: float
    remaining_count: int
    retakes: list[dict] = field(default_factory=list)
    suggested: list[dict] = field(default_factory=list)
    khối_progress: list[dict] = field(default_factory=list)
    off_round: bool = False  # True when the open-class feed offered nothing
    max_tc: float | None = None  # the budget the greedy filled against
    next_semester: str = ""  # extrapolated HK label, e.g. "HK 20253"
    gpa: dict | None = None  # {current_gpa_10/4, direction, delta, ...}
    completion: dict | None = None  # {percent, remaining, total}
    khoi: list[dict] = field(default_factory=list)  # per-khối compliance
    health: dict | None = None  # {failed, d_courses, letters}
    timeline: dict | None = None  # {at_max, at_pace, avg_credits_per_sem}
    fee: dict | None = None  # tuition estimate for the suggested semester

    def as_dict(self) -> dict:
        return {
            "completed_credits": self.completed_credits,
            "remaining_credits": self.remaining_credits,
            "remaining_count": self.remaining_count,
            "retakes": self.retakes,
            "suggested": self.suggested,
            "khối_progress": self.khối_progress,
            "open_round_empty": self.off_round,
            "max_tc": self.max_tc,
            "next_semester": self.next_semester,
            "gpa": self.gpa,
            "completion": self.completion,
            "khoi_compliance": self.khoi,
            "grade_health": self.health,
            "timeline": self.timeline,
            "fee": self.fee,
        }


def _f(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _program_code(api: MyBK) -> str:
    """Profile.curriculum.code (e.g. DH_DHNB_MT_KHM_2023); "" when missing."""
    try:
        info = get_student_info(api)
        return str((info.get("curriculum") or {}).get("code") or "").strip()
    except (ApiError, CasError, requests.RequestException):
        return ""


def _ctdt_courses(api: MyBK, mssv: str) -> list[CtdtCourse]:
    """Normalize live CTĐT rows into CtdtCourse. Retains row for cross-refs."""
    rows = ctdt_courses(api, mssv)
    out: list[CtdtCourse] = []
    for r in rows if isinstance(rows, list) else []:
        if not isinstance(r, dict):
            continue
        out.append(CtdtCourse(
            code=str(r.get("mamonhoc") or "").strip(),
            name=str(r.get("tenmonhoc") or "").strip(),
            credits=_f(r.get("sotc")) or 0.0,
            kind="BB" if str(r.get("khoikienthucbatbuoc")) == "1" else "TC",
            suggested_semester=str(r.get("tenkhoikienthuc") or "").strip(),
            raw=r,
        ))
    return out


def _offered_codes(open_rows: Any) -> dict:
    """mamonhoc -> list of {nhomlop, ...} from the open-class feed."""
    out: dict[str, list] = {}
    for r in open_rows if isinstance(open_rows, list) else []:
        if not isinstance(r, dict) or not r.get("mamonhoc"):
            continue
        out.setdefault(str(r["mamonhoc"]), []).append({
            "nhomlop": r.get("nhomlop"),
            "thoihan": r.get("thoihan"),
        })
    return out


def recommend(
    api: MyBK,
    mssv: str,
    max_tc: float = DEFAULT_MAX_TC,
    semester: str = "",
    program_code: str = "",
) -> PlanResult:
    """Build the next-semester plan from CTĐT + grades + (optional) open feed.

    Pass authority is the GRADE LIST (``diemDat`` in the BANGDIEM_MONHOC rows):
    CTĐT's ``diemdat`` only means "has a grade record", so failed courses would
    otherwise be mis-flagged as completed. ``remaining`` = CTĐT courses with
    credits that are NOT in the passed set (never-taken or taken-but-failed).
    Retakes (grades present but not passed) sort ahead of new courses.
    Remaining credits come from per-khối gaps (tcyeucau−tcdat), not a raw sum
    of every listed elective option.
    """
    courses = _ctdt_courses(api, mssv)
    records = normalize_grade_rows(grades(api, mssv=mssv, tuychon="BANGDIEM_MONHOC"))
    passed = {r.subject_code for r in records if r.passed}
    taken = {r.subject_code for r in records}

    gpa_rows = (xem_ket_qua_hoc_tap(api, mssv) or {}).get("tinChiTichLuy") or []
    trend = analysis.gpa_trend(gpa_rows)

    remaining = [c for c in courses if c.credits > 0 and c.code not in passed and not c.code.startswith("CC")]

    offered: dict[str, list] = {}
    if semester:
        offered = _offered_codes(reg_open_classes(api, semester, "RUTMON"))

    # build PlanCourses
    plans: list[PlanCourse] = []
    for c in remaining:
        plans.append(PlanCourse(
            code=c.code, name=c.name, credits=c.credits,
            khoi=c.suggested_semester,
            douutien=_f(c.raw.get("douutien")) or 0.0,
            status="retake" if c.code in taken else "new",
            offered=c.code in offered,
            groups=offered.get(c.code, []),
        ))

    # A khối can carry multiple ADDITIVE constraints (BB core + elective pool +
    # seminar rows), each repeated with the same (tcyeucau, tcdat) on every
    # course row in its group — dedupe to distinct pairs, then sum per khối so
    # none is dropped (live: Chuyên ngành = 10 BB + 15 tự chọn + 1 seminar =
    # 26 TC; first-row-only read would hide the 9-TC elective gap).
    khối_pairs: dict[str, list[tuple]] = {}
    for c in courses:
        khoi = c.suggested_semester
        if not khoi:
            continue
        req = _f(c.raw.get("tcyeucau")) or 0.0
        done = _f(c.raw.get("tcdat")) or 0.0
        if not req and not done:
            continue  # chứng chỉ/condition rows are not credit constraints
        pair = (round(req, 2), round(done, 2))
        pairs = khối_pairs.setdefault(khoi, [])
        if pair not in pairs:
            pairs.append(pair)

    khối_progress = [
        {
            "khối": khoi,
            "tc_required": round(sum(p[0] for p in pairs), 2),
            "tc_done": round(sum(p[1] for p in pairs), 2),
        }
        for khoi, pairs in khối_pairs.items()
    ]
    khối_progress.sort(key=lambda k: str(k["khối"]))

    unmet_khoi = sum(
        k["tc_required"] - k["tc_done"] for k in khối_progress if k["tc_required"] > k["tc_done"]
    )
    # CTĐT khối totals count failed courses as done, so re-earning them adds back
    retake_credits = sum(p.credits for p in plans if p.status == "retake")

    unmet_khoi_set = {k["khối"] for k in khối_progress if k["tc_required"] > k["tc_done"]}

    def _add(p: PlanCourse) -> bool:
        """Try to append if within budget; returns whether it was added."""
        nonlocal budget
        if budget + p.credits > max_tc:
            return False
        suggested.append(p)
        budget += p.credits
        return True

    # greedy: retakes first; then each unmet khối is filled up to its OWN gap
    # (largest gap first) so one khối can't hog the whole budget while another
    # (e.g. Tốt nghiệp) stays empty; leftover budget spills into met-khối
    # courses by douutien.
    suggested: list[PlanCourse] = []
    budget = 0.0

    for p in plans:
        if p.status == "retake" and not _add(p):
            break

    for k in sorted(
        (k for k in khối_progress if k["tc_required"] > k["tc_done"]),
        key=lambda k: k["tc_required"] - k["tc_done"], reverse=True,
    ):
        gap = k["tc_required"] - k["tc_done"]
        filled = 0.0
        for p in sorted(
            (p for p in plans if p.khoi == k["khối"] and p.status != "retake"),
            key=lambda p: p.douutien, reverse=True,
        ):
            if filled >= gap:
                break  # this khối's hole is covered — move to the next one
            if _add(p):
                filled += p.credits

    for p in sorted(
        (p for p in plans if p.status != "retake" and p.khoi not in unmet_khoi_set),
        key=lambda p: p.douutien, reverse=True,
    ):
        if not _add(p):
            continue

    # count = retakes + rows needed per unmet khối gap (not the full candidate pool)
    remaining_count = 0
    for k in khối_progress:
        if k["tc_required"] <= k["tc_done"]:
            continue
        gap = k["tc_required"] - k["tc_done"]
        khoi_plans = sorted(
            (p for p in plans if p.khoi == k["khối"] and p.status != "retake"),
            key=lambda p: p.douutien, reverse=True,
        )
        acc = 0.0
        for p in khoi_plans:
            remaining_count += 1
            acc += p.credits
            if acc >= gap:
                break
    remaining_count += len([p for p in plans if p.status == "retake"])

    completed = sum(c.credits for c in courses if c.code in passed)

    # Fee stays optional: a profile-fetch failure quietly skips it, and
    # planned_tc counts retakes (suggested holds retakes + new courses).
    program_code = program_code or _program_code(api)
    planned_tc = sum(p.credits for p in suggested)
    fee = fee_estimate(program_code, planned_tc) if program_code else None

    return PlanResult(
        completed_credits=completed,
        remaining_credits=unmet_khoi + retake_credits,
        remaining_count=remaining_count,
        retakes=[p.as_dict() for p in plans if p.status == "retake"],
        suggested=[p.as_dict() for p in suggested if p.status != "retake"],
        khối_progress=khối_progress,
        off_round=semester != "" and not offered,
        max_tc=max_tc,
        next_semester=analysis.next_semester_label(
            trend.get("semesters") or gpa_rows),
        gpa=trend,
        completion=analysis.completion(completed, unmet_khoi + retake_credits),
        khoi=analysis.khoi_compliance(khối_progress),
        health=analysis.grade_health(records),
        timeline=analysis.timeline(unmet_khoi + retake_credits, max_tc, gpa_rows),
        fee=fee,
    )