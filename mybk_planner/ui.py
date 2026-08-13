"""Rich-based pretty renderers for the mybk-planner CLI.

Pure presentation layer: every function receives an already-fetched payload
(dicts from the fetchers, GradeRecord objects, or a PlanResult) and prints it
via the module-level console. No API calls, no imports from cli.py.
"""

from __future__ import annotations

import sys
from collections.abc import Iterable, Sequence
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# cp1252 pipes (legacy console) can't encode Vietnamese — force UTF-8 like cli._print
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

console = Console()

_REG_KEY_ORDER = [
    "id", "nbr", "text", "hockytkb", "mamonhoc", "tenmonhoc",
    "nhomlop", "maHocKyNhomLop", "ngayThi",
]

_BAR_WIDTH = 20


def _fmt(v: Any) -> str:
    """None/empty -> em dash; int-like floats print without the .0."""
    if v is None or v == "":
        return "—"
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def _f(v: Any) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _muted(msg: str) -> None:
    console.print(f"[dim]{msg}[/dim]")


def _pick_keys(row: dict, preferred: Sequence[str], limit: int = 5) -> list[str]:
    """3-5 always-present keys: preferred order first, then raw order."""
    keys = [k for k in preferred if k in row and row.get(k) is not None]
    if len(keys) < 3:
        for k in row:
            if k not in keys and row.get(k) is not None:
                keys.append(k)
            if len(keys) >= limit:
                break
    return keys[:limit]


def _table_from_dicts(rows: list, preferred: Sequence[str], title: str | None = None) -> None:
    if not rows:
        _muted("— không có dữ liệu (ngoài đợt?).")
        return
    dicts = [r for r in rows if isinstance(r, dict)]
    if not dicts:
        console.print(str(rows[0]))
        return
    keys = _pick_keys(dicts[0], preferred)
    table = Table(title=title, header_style="bold cyan")
    for k in keys:
        table.add_column(str(k))
    for r in dicts:
        table.add_row(*[_fmt(r.get(k)) for k in keys])
    console.print(table)


def _bar(done: float, required: float, width: int = _BAR_WIDTH) -> Text:
    ratio = max(0.0, min(1.0, done / required)) if required > 0 else 0.0
    filled = round(width * ratio)
    text = Text()
    text.append("█" * filled, style="green")
    text.append("░" * (width - filled), style="dim")
    return text


def _khoi_bars(progress: Iterable[dict]) -> None:
    """Shared per-khối credit bars: items carry khối / tc_required / tc_done."""
    for item in progress:
        if not isinstance(item, dict):
            continue
        khoi = item.get("khối") or item.get("tenkhoikienthuc") or "?"
        required = _f(item.get("tc_required") or item.get("tcyeucau")) or 0.0
        done = _f(item.get("tc_done") or item.get("tcdat")) or 0.0
        if not required and not done:
            continue
        line = Text(f"{khoi}: {_fmt(done)}/{_fmt(required)} ")
        line.append_text(_bar(done, required))
        console.print(line)


def render_info(profile: Any) -> None:
    if not isinstance(profile, dict) or not profile:
        _muted("— không có dữ liệu hồ sơ.")
        return
    table = Table(title="Thông tin sinh viên", header_style="bold cyan")
    table.add_column("Trường")
    table.add_column("Giá trị")
    for key, value in profile.items():
        if value in (None, ""):
            continue
        table.add_row(str(key), _fmt(value))
    console.print(table)


def render_grades(records: list, summary: dict) -> None:
    if not records:
        _muted("— không có điểm.")
        return
    groups: dict = {}
    for r in records:
        sem = _fmt(r.semester)
        groups.setdefault(sem, []).append(r)
    # numeric semesters first (ascending), then non-semester ("BL", "—") last
    for sem in sorted(groups, key=lambda s: (not str(s).isdigit(), str(s))):
        table = Table(title=f"Bảng điểm — HK {sem}", header_style="bold cyan")
        for col in ("Mã MH", "Tên", "TC", "Điểm 10", "Điểm chữ", "Kết quả"):
            table.add_column(col)
        for r in groups[sem]:
            result = Text("Đạt", style="green") if r.passed else Text("Rớt", style="red")
            table.add_row(
                _fmt(r.subject_code), _fmt(r.subject_name), _fmt(r.credits),
                _fmt(r.score_10), _fmt(r.letter), result,
            )
        console.print(table)
    if summary:
        console.print(
            f"[bold]Tổng: {_fmt(summary.get('total'))} | "
            f"Đạt: {_fmt(summary.get('passed'))} | "
            f"Rớt: {_fmt(summary.get('failed'))} | "
            f"Có thể cải thiện (D): {_fmt(summary.get('improvable_D'))} | "
            f"TB hệ 10: {_fmt(summary.get('mean_score_10'))}[/bold]"
        )


def render_gpa(header: Any, gpa: dict) -> None:
    lines: list[str] = []
    if isinstance(header, dict):
        name = next((header[k] for k in ("hoten", "hoTen", "ten", "masv", "maSV")
                     if header.get(k)), None)
        if name:
            lines.append(str(name))
    lines.append(f"GPA hệ 4:  {_fmt(gpa.get('gpa_4'))}")
    lines.append(f"GPA hệ 10: {_fmt(gpa.get('gpa_10'))}")
    lines.append(f"Số TC tích lũy: {_fmt(gpa.get('credits'))}")
    console.print(Panel("\n".join(lines), title="GPA"))


def render_ctdt(courses: list) -> None:
    rows = [c for c in courses if isinstance(c, dict)] if isinstance(courses, list) else []
    table = Table(title="Chương trình đào tạo", header_style="bold cyan")
    for col in ("Khối", "Mã MH", "Tên môn", "TC", "Điểm", "Trạng thái"):
        table.add_column(col)
    progress: list[dict] = []
    seen_khoi = set()
    for c in rows:
        khoi = str(c.get("tenkhoikienthuc") or "").strip()
        if khoi and khoi not in seen_khoi:
            seen_khoi.add(khoi)
            progress.append(c)  # first row per khối carries tcyeucau/tcdat
        code = str(c.get("mamonhoc") or "").strip()
        if not code:
            continue
        # diemdat=="1" means "has a grade record" (NOT passed); tamdat = tạm đạt
        if str(c.get("diemdat")) == "1":
            status = Text("Đạt", style="green")
        elif str(c.get("tamdat")) == "1":
            status = Text("Tạm đạt", style="yellow")
        else:
            status = Text("Còn lại", style="white")
        diem = next((c[k] for k in ("diem", "diemso", "diem10", "diemTongKet")
                     if c.get(k) not in (None, "")), None)
        table.add_row(khoi or "—", code, _fmt(c.get("tenmonhoc")),
                      _fmt(c.get("sotc")), _fmt(diem), status)
    console.print(table)
    _khoi_bars(progress)


def render_reg(tag: str, payload: Any) -> None:
    console.print(Panel(tag, title=tag))
    if payload in (None, [], {}):
        _muted("— không có dữ liệu (ngoài đợt?).")
        return
    if isinstance(payload, list):
        _table_from_dicts(payload, _REG_KEY_ORDER)
    elif isinstance(payload, dict):
        render_info(payload)
    else:
        console.print(str(payload))


def render_error(exc: BaseException) -> None:
    console.print(Panel(f"[bold red]Lỗi: {exc}[/bold red]", style="red"))


def render_dashboard(profile: Any, gpa: dict, plan: Any) -> None:
    if isinstance(profile, dict) and profile:
        # two shapes: VPN-style (hoten) and raw info dict (lastName + firstName)
        name = profile.get("hoten") or " ".join(
            p for p in (profile.get("lastName"), profile.get("firstName")) if p
        ) or "—"
        masv = next((profile[k] for k in ("code", "maSinhVien", "masv", "id")
                     if profile.get(k) not in (None, "")), "—")
        lop = profile.get("lop") or profile.get("classCode") or "—"
        khoa = profile.get("khoa") or (profile.get("major") or {}).get("nameVi") or "—"
        info_line = f"{name} — {masv} — {lop} — {khoa}"
    else:
        info_line = "— không có dữ liệu hồ sơ."
    console.print(Panel(info_line, title="Sinh viên"))
    render_gpa(None, gpa)
    header = (
        f"TC đã hoàn thành: {_fmt(getattr(plan, 'completed_credits', None))} | "
        f"TC còn lại: {_fmt(getattr(plan, 'remaining_credits', None))}"
    )
    console.print(Panel(header, title="Kế hoạch"))
    _khoi_bars(getattr(plan, "khối_progress", None) or [])
