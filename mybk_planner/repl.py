"""Interactive REPL for mybk-planner — one CAS login, then a menu loop.

Run directly (``python -m mybk_planner.repl``) or via ``python -m
mybk_planner.cli`` with no subcommand. Read-only: every menu entry is a
fetch rendered through ui.py; a failed fetch prints an error and returns
to the prompt instead of dying.
"""

from __future__ import annotations

import re
import sys

import requests
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
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
)

_SEMESTER_RE = re.compile(r"^\d{4}[1-3]$")  # YYYYk semester code, e.g. 20252

_HELP_OVERVIEW = """\
[bold]Lệnh REPL — gõ `help <lệnh>` hoặc `help all` để xem chi tiết từng lệnh[/bold]

  [cyan]1[/cyan] | info          Hồ sơ sinh viên
  [cyan]2[/cyan] | grades        Bảng điểm (kèm danh sách môn chưa đạt)
  [cyan]3[/cyan] | gpa           GPA tích lũy (hệ 4 + hệ 10)
  [cyan]4[/cyan] | ctdt          Chương trình đào tạo (toàn bộ môn + tiến độ theo khối)
  [cyan]5[/cyan] | plan [hk]     Kế hoạch học tập gợi ý (vd: [i]5 20253[/i])
  [cyan]6[/cyan] | schedule [hk] Thời khóa biểu (vd: [i]6 20252[/i])
  [cyan]7[/cyan] | exams <nh> <hk>  Lịch thi (vd: [i]7 2025 2[/i])
  [cyan]8[/cyan] | dash          Dashboard: info + GPA + plan
  [cyan]f[/cyan] | find <từ khóa>   Tìm môn trong CTĐT (mã hoặc tên, tối đa 15 kết quả)

  exit | quit | q     Thoát (Ctrl+C quay lại prompt, Ctrl+D thoát)
  help [lệnh]         Xem chi tiết; `help all` xem hết
"""

_HELP_DETAIL = {
    "info": (
        "info — Hồ sơ sinh viên\n"
        "  Không cần tham số. Trả về mã số, họ tên, lớp, khoa…"
    ),
    "grades": (
        "grades — Bảng điểm\n"
        "  Không cần tham số. Hiển thị toàn bộ điểm đã học, chia theo từng học kỳ,\n"
        "  kèm tóm tắt (tổng/đạt/rớt, số môn điểm D có thể cải thiện, TB hệ 10)\n"
        "  và bảng các môn chưa đạt."
    ),
    "gpa": (
        "gpa — GPA tích lũy\n"
        "  Không cần tham số. GPA hệ 4, hệ 10 và số tín chỉ tích lũy."
    ),
    "ctdt": (
        "ctdt — Chương trình đào tạo\n"
        "  Không cần tham số. Danh sách toàn bộ môn theo CTĐT, trạng thái từng môn\n"
        "  (đạt/tạm đạt/còn lại) và thanh tiến độ tín chỉ theo từng khối kiến thức."
    ),
    "plan": (
        "plan [hk] — Kế hoạch học tập gợi ý\n"
        "  [hk]  (tùy chọn) mã học kỳ dạng YYYYk, vd: 20253. Bỏ trống = dùng CTĐT\n"
        "        + điểm đã có để gợi ý học kỳ tiếp theo.\n"
        "  Ví dụ:  5 20253"
    ),
    "schedule": (
        "schedule [hk] — Thời khóa biểu\n"
        "  [hk]  (tùy chọn) mã học kỳ dạng [i]YYYYk[/i] (năm + số HK 1-3), vd: 20252.\n"
        "        Bỏ trống = học kỳ hiện tại. Lưu ý: đây là mã học kỳ (5 số), KHÔNG phải\n"
        "        năm dạng 4 số như 2025.\n"
        "  Ví dụ:  6 20252\n"
        "         6 20253"
    ),
    "exams": (
        "exams <năm học> <học kỳ> — Lịch thi\n"
        "  <năm học>  năm dạng 4 số, vd: 2025 (server không nhận dạng 2025-2026).\n"
        "  <học kỳ>   số 1-3 (1=GK, 2=CK…), vd: 2.\n"
        "  Ví dụ:  7 2025 2"
    ),
    "dash": (
        "dash — Dashboard\n"
        "  Không cần tham số. Gộp info + GPA + kế hoạch trong một lần đăng nhập."
    ),
    "find": (
        "find <từ khóa> — Tìm môn trong CTĐT\n"
        "  <từ khóa>  mã môn (vd: CO1027) hoặc một phần tên môn. Khớp không phân\n"
        "             biệt hoa thường, hiển thị tối đa 15 kết quả.\n"
        "  Ví dụ:  find CO1027\n"
        "          find Web"
    ),
}

_COMMANDS = "info grades gpa ctdt plan schedule exams dash find"

_ALIASES = {
    "1": "info", "2": "grades", "3": "gpa", "4": "ctdt", "5": "plan",
    "6": "schedule", "7": "exams", "8": "dash",
    "f": "find", "h": "help", "?": "help", "q": "exit",
}


def _print_help(topic: str = "") -> None:
    topic = _ALIASES.get(topic, topic).strip().lower()
    if not topic:
        console.print(_HELP_OVERVIEW)
        return
    if topic == "all":
        console.print(_HELP_OVERVIEW)
        for body in _HELP_DETAIL.values():
            console.print(f"\n{body}")
        return
    if topic in _HELP_DETAIL:
        console.print(_HELP_DETAIL[topic])
        return
    if topic in ("exit", "quit"):
        console.print("exit | quit | q — Thoát (Ctrl+C quay lại prompt, Ctrl+D thoát).")
        return
    console.print(
        f"[yellow]Không có trợ giúp cho '{topic}'. Lệnh hiện có: {_COMMANDS}.[/yellow]"
    )

_FETCH_ERRORS = (CasError, ApiError, requests.RequestException, dkmh.DkmhError)


def _resolve_sid(api: MyBK, env: dict | None = None) -> str:
    """Same profile-guess as cli._pron: code/maSinhVien/mssv/maSV/studentId/id,
    then the MYBK_MSSV env var as a last resort."""
    try:
        profile = get_student_info(api)
    except _FETCH_ERRORS:
        profile = None
    if isinstance(profile, dict):
        for k in ("code", "maSinhVien", "mssv", "maSV", "studentId", "id"):
            v = profile.get(k)
            if v not in (None, "", 0):
                return str(v)
    return resolve("MYBK_MSSV", env or {}, aliases=("MYBK_TEST_MSSV",)) or ""


def _login(env_path=None, username=None, password=None) -> tuple[MyBK, str]:
    env = load_env_file(env_path or default_env_path())
    user = resolve("MYBK_USERNAME", env, username, aliases=("MYBK_TEST_USERNAME",))
    pw = resolve("MYBK_PASSWORD", env, password, aliases=("MYBK_TEST_PASSWORD",))
    if not user or not pw:
        raise CasError(
            "missing credentials — export MYBK_USERNAME/MYBK_PASSWORD "
            "or keep a .env next to the repo"
        )
    session, jwt = login_app(user, pw)
    api = MyBK(session, jwt)
    return api, _resolve_sid(api, env)


def _failed_table(failed) -> Table:
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


def _find(api: MyBK, sid: str, query: str) -> None:
    """Fuzzy CTĐT search: mamonhoc OR tenmonhoc contains query (case-insensitive)."""
    rows = ctdt_courses(api, mssv=sid)
    q = query.casefold()
    matches = []
    for r in rows if isinstance(rows, list) else []:
        if not isinstance(r, dict):
            continue
        code = str(r.get("mamonhoc") or "")
        name = str(r.get("tenmonhoc") or "")
        if q in code.casefold() or q in name.casefold():
            matches.append(r)
    if not matches:
        console.print(f"[yellow]Không thấy môn nào khớp '{query}'.[/yellow]")
        return
    t = Table(title=f"Tìm '{query}': {len(matches)} môn (hiển thị tối đa 15)")
    t.add_column("Mã MH", style="cyan")
    t.add_column("Tên môn")
    t.add_column("TC", justify="right")
    t.add_column("Khối")
    for r in matches[:15]:
        t.add_row(
            str(r.get("mamonhoc") or ""),
            str(r.get("tenmonhoc") or ""),
            str(r.get("sotc") or ""),
            str(r.get("tenkhoikienthuc") or ""),
        )
    console.print(t)


def _dispatch(api: MyBK, sid: str, cmd: str, rest: str) -> None:
    if cmd in ("1", "info"):
        render_info(get_student_info(api))
        return
    if cmd in ("2", "grades"):
        records = normalize_grade_rows(grades(api, mssv=sid))
        summary = summarize_grades(records)
        render_grades(records, summary)
        failed = summary.get("failed_records", [])
        if failed:
            console.print(_failed_table(failed))
        return
    if cmd in ("3", "gpa"):
        render_gpa(transcript_summary(api, mssv=sid), gpa_summary(api, mssv=sid))
        return
    if cmd in ("4", "ctdt"):
        render_ctdt(ctdt_courses(api, mssv=sid))
        return
    if cmd in ("5", "plan"):
        result = plan_recommend(api, mssv=sid, semester=rest)
        render_plan(result)
        render_plan_analysis(result)
        return
    if cmd in ("6", "schedule"):
        # 4-digit years like 2025 hit the API and silently return empty ("no data")
        # — reject them here as a usage error instead of reusing that message.
        if rest and not _SEMESTER_RE.match(rest):
            console.print(
                "[yellow]Sai mã học kỳ. Dùng: 6 <mã học kỳ YYYYk> — vd: 6 20252 "
                "(bỏ trống = học kỳ hiện tại). Không phải năm 4 số.[/yellow]"
            )
            return
        rows = fetch_schedule(api, sid, rest)
        if rest == "" and not rows:
            # Current semester has no published schedule yet (off-season) — the
            # blank default reads as "no data"; point at an explicit semester.
            console.print(
                "[yellow]Học kỳ hiện tại chưa có thời khóa biểu. Dùng: 6 20252 (hoặc "
                "mã YYYYk của học kỳ bạn cần).[/yellow]"
            )
            return
        render_schedule(rows)
        return
    if cmd in ("7", "exams"):
        parts = rest.split()
        if len(parts) < 2:
            console.print("[yellow]Dùng: 7 <năm học> <học kỳ> — vd: 7 2025 2[/yellow]")
            return
        render_exams(fetch_exams(api, sid, parts[0], parts[1]))
        return
    if cmd in ("8", "dash", "dashboard"):
        profile = get_student_info(api)
        gpa = gpa_summary(api, mssv=sid)
        plan = plan_recommend(api, mssv=sid)
        render_dashboard(profile, gpa, plan)
        return
    if cmd == "find":
        if not rest:
            console.print("[yellow]Dùng: find <mã môn|từ khóa> — vd: find CO1027[/yellow]")
            return
        _find(api, sid, rest)
        return
    console.print(f"[yellow]Lệnh không rõ: {cmd!r} — gõ 'help' để xem danh sách.[/yellow]")


def _make_prompt() -> PromptSession | None:
    """Rich prompt when a console exists; None (→ plain input()) in pipes/CI,
    where prompt_toolkit has no output buffer to draw to."""
    try:
        return PromptSession(history=InMemoryHistory())
    except Exception:  # noqa: BLE001 — any prompt failure degrades to plain input()
        return None


def run(args=None) -> int:
    """Login once, then loop the menu prompt. Returns the process exit code."""
    try:
        api, sid = _login(
            getattr(args, "env", None),
            getattr(args, "username", None),
            getattr(args, "password", None),
        )
    except _FETCH_ERRORS as e:
        render_error(e)
        return 1
    hello = "[green]Đăng nhập thành công[/green]"
    if sid:
        hello += f" — MSSV [bold]{sid}[/bold]"
    console.print(hello)
    console.print(_HELP_OVERVIEW)
    prompt = _make_prompt()
    while True:
        try:
            line = prompt.prompt("mybk> ") if prompt is not None else input("mybk> ")
            line = line.strip()
        except KeyboardInterrupt:
            continue  # Ctrl+C quay lại prompt
        except EOFError:
            console.print("Tạm biệt.")
            return 0
        if not line:
            continue
        cmd, _, rest = line.partition(" ")
        cmd, rest = cmd.lower(), rest.strip()
        if cmd in ("exit", "quit", "q"):
            console.print("Tạm biệt.")
            return 0
        if cmd in ("help", "h", "?"):
            _print_help(rest)
            continue
        try:
            _dispatch(api, sid, cmd, rest)
        except KeyboardInterrupt:
            console.print("[dim]Đã hủy — quay lại prompt.[/dim]")
        except _FETCH_ERRORS as e:
            render_error(e)
        except Exception as e:  # noqa: BLE001 — unexpected; keep the loop alive
            render_error(e)


def main() -> int:
    return run(None)


if __name__ == "__main__":
    sys.exit(main())
