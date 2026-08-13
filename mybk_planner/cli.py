"""mybk-planner CLI — read-only data fetchers for the HCMUT portal.

Usage:
    python -m mybk_planner.cli                # no subcommand -> interactive REPL
    python -m mybk_planner.cli auth [--env PATH]
    python -m mybk_planner.cli info            # student profile (SID, faculty)
    python -m mybk_planner.cli grades          # all grades (BANGDIEM_MONHOC)
    python -m mybk_planner.cli gpa             # cumulative GPA
    python -m mybk_planner.cli ctdt            # CTĐT course list (planner master-plan)
    python -m mybk_planner.cli schedule [--student-id 2212345] [--semester-year 20252]
    python -m mybk_planner.cli exams [--mssv 2212345] --namhoc 2025 --hocky 2
    python -m mybk_planner.cli dashboard       # Info + GPA + Plan in one view
    # Modern /app sinh-vien/* registration surface (read-only, verified 2026-08-14):
    python -m mybk_planner.cli reg-dots          # current đợt(s) for a feed type
    python -m mybk_planner.cli reg-open-classes --hockytkb 20253
    python -m mybk_planner.cli reg-tickets       # own pending + finished tickets
    python -m mybk_planner.cli reg-defer --hocky 20253 --dot HOANTHI_CK.20253.1
    python -m mybk_planner.cli reg-profile       # own registrant profile
    python -m mybk_planner.cli plan --max-tc 18 [--semester 20253]  # suggest next-semester plan

Every command renders a pretty table view by default; pass --json for the raw
JSON payload (byte-compatible with the original scriptable output).
Envelope quirk: `code: "400"` carries business rows; callers receive `data`.
All tools exit 0 on success, 1 on auth/API/DKMH errors.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import requests
from rich.table import Table

from . import open_classes as dkmh
from .api import ApiError, MyBK
from .cas import CasError, login_app
from .env import default_env_path, load_env_file, resolve
from .planner import recommend as plan_recommend
from .planview import render_plan, render_plan_analysis
from .timetable import exams as fetch_exams
from .timetable import schedule as fetch_schedule
from .timetable_view import render_exams, render_schedule
from .transcript import (
    ctdt_courses,
    get_student_info,
    gpa_summary,
    grades,
    normalize_grade_rows,
    recompute_own_gpa,
    summarize_grades,
    transcript_summary,
)
from .ui import (
    console,
    render_ctdt,
    render_dashboard,
    render_error,
    render_gpa,
    render_grades,
    render_info,
    render_reg,
)


def _print(data: Any) -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def _die(msg: str) -> int:
    print(f"error: {msg}", file=sys.stderr)
    return 1


def _env(args) -> dict:
    return load_env_file(args.env or default_env_path())


def _creds(args) -> dict:
    env = _env(args)
    return {
        "username": resolve("MYBK_USERNAME", env, args.username, aliases=("MYBK_TEST_USERNAME",)),
        "password": resolve("MYBK_PASSWORD", env, args.password, aliases=("MYBK_TEST_PASSWORD",)),
    }


def _session(args) -> requests.Session:
    creds = _creds(args)
    if not creds["username"] or not creds["password"]:
        raise CasError(
            "missing credentials — export MYBK_USERNAME/MYBK_PASSWORD "
            "or pass --env </abs/path/.env>"
        )
    session, jwt = login_app(creds["username"], creds["password"])
    if not getattr(args, "json", False):
        console.print("[green]Đăng nhập thành công.[/green]")
    return session, jwt


def _api(args) -> MyBK:
    session, jwt = _session(args)
    return MyBK(session, jwt)


def _pron(api: MyBK, args=None) -> str:
    """Resolve the maSinhVien body value: prefers the mssv `code` field,
    falls back to the internal numeric id, then to the MYBK_MSSV env var."""
    try:
        profile = get_student_info(api)
    except (ApiError, CasError, requests.RequestException):
        profile = None
    if isinstance(profile, dict):
        for k in ("code", "maSinhVien", "mssv", "maSV", "studentId", "id"):
            v = profile.get(k)
            if v not in (None, "", 0):
                return str(v)
    env = _env(args) if args is not None else load_env_file(default_env_path())
    return resolve("MYBK_MSSV", env, aliases=("MYBK_TEST_MSSV",)) or ""


def _failed_table(failed) -> Table:
    """Small red table of not-passed grade records (pretty path only)."""
    t = Table(title="Môn chưa đạt", style="red", header_style="bold red")
    t.add_column("Mã MH")
    t.add_column("Tên môn")
    t.add_column("Điểm", justify="right")
    t.add_column("HK")
    for r in failed:
        t.add_row(
            str(r.subject_code or ""),
            str(r.subject_name or ""),
            "" if r.score_10 is None else str(r.score_10),
            str(r.semester or ""),
        )
    return t


def _banner() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("mybk-planner — HCMUT course-planner (read-only)")
    print("Lệnh: auth | info | grades | gpa | ctdt | schedule | exams | dashboard | plan | reg-*")
    print("Mặc định in dạng bảng; thêm --json để lấy JSON thô. '<lệnh> -h' để xem tham số.")
    print("Không có lệnh -> vào REPL tương tác (gõ 'help' trong REPL, 'exit' để thoát).\n")


def run(args) -> int:
    as_json = getattr(args, "json", False)
    try:
        if args.cmd == "auth":
            _, jwt = _session(args)
            if as_json:
                _print({"authenticated": True, "app": "https://mybk.hcmut.edu.vn/app/",
                        "jwt_prefix": jwt[:40] + "…"})
            return 0
        if args.cmd == "info":
            profile = get_student_info(_api(args))
            if as_json:
                _print(profile)
            else:
                render_info(profile)
            return 0
        if args.cmd == "grades":
            api = _api(args)
            sid = _pron(api, args)
            rows = grades(api, mssv=sid, tuychon=args.tuychon)
            records = normalize_grade_rows(rows)
            summary = summarize_grades(records)
            if as_json:
                _print({"raw_count": len(rows) if isinstance(rows, list) else "?", "summary": summary,
                        "passed": [r.raw for r in records if r.passed],
                        "failed": [r.raw for r in summary.get("failed_records", [])]})
            else:
                render_grades(records, summary)
                failed = summary.get("failed_records", [])
                if failed:
                    console.print(_failed_table(failed))
            return 0
        if args.cmd == "gpa":
            api = _api(args)
            sid = _pron(api, args)
            recompute = recompute_own_gpa(api)
            summary = gpa_summary(api, mssv=sid)
            header = transcript_summary(api, mssv=sid)
            if as_json:
                _print({"recompute": recompute, "student_id": sid, "header": header, "gpa": summary})
            else:
                render_gpa(header, summary)
            return 0
        if args.cmd == "ctdt":
            api = _api(args)
            sid = _pron(api, args)
            courses = ctdt_courses(api, mssv=sid)
            if as_json:
                _print({"course_count": len(courses) if isinstance(courses, list) else "?",
                        "courses": courses})
            else:
                render_ctdt(courses)
            return 0
        if args.cmd == "schedule":
            api = _api(args)
            sid = args.student_id or _pron(api, args)
            payload = fetch_schedule(api, sid, args.semester_year)
            if as_json:
                _print(payload)
            else:
                render_schedule(payload)
            return 0
        if args.cmd == "exams":
            api = _api(args)
            mssv = args.mssv or _pron(api, args)
            payload = fetch_exams(api, mssv, args.namhoc, args.hocky)
            if as_json:
                _print(payload)
            else:
                render_exams(payload)
            return 0
        if args.cmd == "reg-dots":
            api = _api(args)
            payload = dkmh.reg_dots(api, args.reg_type, args.loai_dang_ky_id)
            if as_json:
                _print({"dots": payload})
            else:
                render_reg("dots", payload)
            return 0
        if args.cmd == "reg-open-classes":
            api = _api(args)
            payload = dkmh.reg_open_classes(api, args.hockytkb, args.reg_type)
            if as_json:
                _print({"open_classes": payload})
            else:
                render_reg("open-classes", payload)
            return 0
        if args.cmd == "reg-tickets":
            api = _api(args)
            payload = dkmh.reg_my_tickets(api, args.loai_dang_ky_id)
            if as_json:
                _print(payload)
            else:
                render_reg("tickets", payload)
            return 0
        if args.cmd == "reg-defer":
            api = _api(args)
            payload = {
                "semesters": dkmh.reg_defer_semesters(api),
                "dot": dkmh.reg_defer_dot(api, args.hocky) if args.hocky else None,
                "courses": dkmh.reg_defer_exam_courses(api, args.dot) if args.dot else None,
            }
            if as_json:
                _print(payload)
            else:
                render_reg("defer", payload)
            return 0
        if args.cmd == "reg-profile":
            payload = dkmh.reg_own_profile(_api(args))
            if as_json:
                _print(payload)
            else:
                render_reg("profile", payload)
            return 0
        if args.cmd == "plan":
            api = _api(args)
            sid = _pron(api, args)
            result = plan_recommend(api, mssv=sid, max_tc=args.max_tc, semester=args.semester)
            if as_json:
                _print({"student_id": sid, "plan": result.as_dict()})
            else:
                render_plan(result)
                render_plan_analysis(result)
            return 0
        if args.cmd == "dashboard":
            api = _api(args)
            sid = _pron(api, args)
            profile = get_student_info(api)
            gpa = gpa_summary(api, mssv=sid)
            plan = plan_recommend(api, mssv=sid, max_tc=args.max_tc, semester=args.semester)
            if as_json:
                _print({"student_id": sid, "profile": profile, "gpa": gpa, "plan": plan.as_dict()})
            else:
                render_dashboard(profile, gpa, plan)
            return 0
        return _die(f"unknown command: {args.cmd}")
    except (CasError, ApiError, requests.RequestException, dkmh.DkmhError) as e:
        if as_json:
            return _die(str(e))
        render_error(e)
        return 1


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="mybk-planner", description="HCMUT course-planner data layer (read-only)")
    cred = argparse.ArgumentParser(add_help=False)
    cred.add_argument("--env", default=None, help="path to .env (KEY=VALUE)")
    cred.add_argument("--username")
    cred.add_argument("--password")
    cred.add_argument("--json", action="store_true", help="raw JSON output (scriptable)")
    p.add_argument("--env", default=None, help=argparse.SUPPRESS)  # also on main, for `planner --env X <cmd>`
    p.add_argument("--username", help=argparse.SUPPRESS)
    p.add_argument("--password", help=argparse.SUPPRESS)
    p.add_argument("--json", action="store_true", help="raw JSON output (scriptable)")
    sub = p.add_subparsers(dest="cmd")

    def add(name, *args, **kw):
        return sub.add_parser(name, *args, parents=[cred], **kw)

    add("auth")
    add("info")
    g = add("grades")
    g.add_argument("--tuychon", default="BANGDIEM_MONHOC")
    add("gpa")
    add("ctdt")
    s = add("schedule")
    s.add_argument("--student-id", default="", help="mssv; bỏ trống = tự lấy từ hồ sơ")
    s.add_argument("--semester-year", default="", help="YYYYk semester code, e.g. 20252 (blank = mặc định)")
    e = add("exams")
    e.add_argument("--mssv", default="", help="mssv; bỏ trống = tự lấy từ hồ sơ")
    e.add_argument("--namhoc", required=True, help="numeric year e.g. 2025 (server rejects 2025-2026)")
    e.add_argument("--hocky", required=True, help="e.g. 2")
    rd = add("reg-dots", help="modern /app: current registration đợt(s)")
    rd.add_argument("--reg-type", default="RUTMON")
    rd.add_argument("--loai-dang-ky-id", default=dkmh.RUTMON_LOAI_DANG_KY_ID)
    ro = add("reg-open-classes", help="modern /app: open classes for a semester")
    ro.add_argument("--hockytkb", required=True, help="e.g. 20253 (from reg-dots)")
    ro.add_argument("--reg-type", default="RUTMON")
    rt = add("reg-tickets", help="modern /app: own pending+finished tickets")
    rt.add_argument("--loai-dang-ky-id", default=dkmh.RUTMON_LOAI_DANG_KY_ID)
    rdf = add("reg-defer", help="modern /app: hoãn-thi đợt + exam rows")
    rdf.add_argument("--hocky", default="", help="semester code e.g. 20253 (omit to skip dot)")
    rdf.add_argument("--dot", default="", help="đợt code e.g. HOANTHI_CK.20253.1 (omit to skip rows)")
    add("reg-profile", help="modern /app: own registrant profile")

    pl = add("plan", help="CTĐT + grades (+ open feed) -> suggested next-semester plan")
    pl.add_argument("--max-tc", type=float, default=18.0, help="per-semester credit budget (default 18.0 = HCMUT định mức)")
    pl.add_argument("--semester", default="", help="hockytkb e.g. 20253: annotate offered codes from the open-class feed")

    d = add("dashboard", help="Info + GPA + Plan gọn trong một màn hình (một lần đăng nhập)")
    d.add_argument("--max-tc", type=float, default=18.0, help="per-semester credit budget (default 18.0 = HCMUT định mức)")
    d.add_argument("--semester", default="", help="hockytkb e.g. 20253 (optional, như plan)")

    args = p.parse_args(argv)
    if args.cmd is None:
        _banner()
        from . import repl
        return repl.run(args)
    return run(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
