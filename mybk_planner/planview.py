"""Rich renderers for plan output — the analysis-heavy view.

Separated from ui.py (which owns the simple data renderers) so the plan view,
with its trend / completion / khối-compliance / health / timeline sections,
stays reviewable on its own. Reuses ui.py's shared formatting helpers.
"""

from __future__ import annotations

from typing import Any

from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .ui import _bar, _f, _fmt, _khoi_bars, _muted, console

_DIR_STYLE = {"up": "green", "down": "red3", "flat": "yellow", "unknown": "dim"}


def _plan_course_table(title: str, courses: list, retake: bool) -> None:
    table = Table(title=title, header_style="bold cyan")
    if retake:
        for col in ("Mã MH", "Tên", "TC", "Khối", "Trạng thái"):
            table.add_column(col)
        for c in courses:
            table.add_row(_fmt(c.get("code")), _fmt(c.get("name")), _fmt(c.get("credits")),
                          _fmt(c.get("khoi")), Text("Học lại", style="red"))
    else:
        for col in ("Mã MH", "Tên", "TC", "Khối", "Ưu tiên", "Mở lớp"):
            table.add_column(col)
        for c in courses:
            mark = Text("✓", style="green") if c.get("offered") else Text("•", style="gold3")
            table.add_row(_fmt(c.get("code")), _fmt(c.get("name")), _fmt(c.get("credits")),
                          _fmt(c.get("khoi")), _fmt(c.get("douutien")), mark)
    console.print(table)


def _trend_line(gpa: dict | None) -> str:
    if not gpa or gpa.get("current_gpa_10") is None:
        return "— chưa có dữ liệu GPA."
    d = _DIR_STYLE.get(gpa.get("direction"), "dim")
    delta = _fmt(gpa.get("delta"))
    recent = _fmt(gpa.get("recent_delta"))
    return (
        f"GPA hiện tại: [bold]{_fmt(gpa.get('current_gpa_10'))}[/bold] hệ 10 "
        f"([bold]{_fmt(gpa.get('current_gpa_4'))}[/bold] hệ 4) · "
        f"xu hướng [[{d}]{gpa.get('direction')}[/{d}]] "
        f"(tổng {delta}, 2 HK gần đây {recent})"
    )


def render_gpa_trend(gpa: dict | None) -> None:
    sems = (gpa or {}).get("semesters") or []
    if not sems:
        _muted("— chưa có dữ liệu GPA theo học kỳ.")
        return
    table = Table(title="GPA tích lũy theo học kỳ", header_style="bold cyan")
    for col in ("HK", "GPA 10", "GPA 4", "TC"):
        table.add_column(col)
    for s in sems:
        table.add_row(str(s.get("hk")), _fmt(s.get("gpa_10")),
                      _fmt(s.get("gpa_4")), _fmt(s.get("credits")))
    console.print(table)


def _completion_block(completion: dict | None) -> None:
    if not completion:
        return
    pct = _fmt(completion.get("percent"))
    done = _fmt(completion.get("completed"))
    total = _fmt(completion.get("total"))
    remaining = _fmt(completion.get("remaining"))
    console.print(
        f"Hoàn thành chương trình: [bold]{pct}%[/bold] "
        f"({done}/{total} TC — còn [bold]{remaining}[/bold] TC)"
    )
    console.print(_bar(float(completion.get("percent", 0) or 0), 100.0))


def render_khoi_compliance(khoi: list[dict]) -> None:
    short = [k for k in khoi if not k.get("met")]
    if not short:
        return
    table = Table(title="Khối kiến thức còn thiếu", header_style="bold cyan")
    for col in ("Khối", "Yêu cầu", "Đã đạt", "Còn thiếu"):
        table.add_column(col)
    for k in short:
        table.add_row(str(k.get("khoi")), _fmt(k.get("required")),
                      _fmt(k.get("done")), Text(_fmt(k.get("gap")), style="red3"))
    console.print(table)


def render_grade_health(health: dict | None) -> None:
    if not health:
        return
    letters = health.get("letters") or {}
    total = sum(letters.values())
    if not total:
        return
    parts = " · ".join(f"{k}: {n}" for k, n in sorted(letters.items()) if n)
    console.print(f"[dim]Phân bố điểm: {parts}[/dim]")
    failed = health.get("failed") or []
    if failed:
        console.print(
            f"[red3]⚠ {len(failed)} môn chưa đạt cần học lại "
            f"({', '.join(f['code'] for f in failed)}) — chiếm chỗ học kỳ tới.[/red3]"
        )
    d_courses = health.get("d_courses") or []
    if d_courses:
        console.print(
            f"[yellow]💡 {len(d_courses)} môn điểm D có thể cải thiện để tăng GPA.[/yellow]"
        )


def render_plan(result: Any) -> None:
    header = (
        f"TC đã hoàn thành: {_fmt(getattr(result, 'completed_credits', None))}\n"
        f"TC còn lại: {_fmt(getattr(result, 'remaining_credits', None))} "
        f"(~{_fmt(getattr(result, 'remaining_count', None))} môn)"
    )
    console.print(Panel(header, title="Kế hoạch học kỳ"))
    retakes = getattr(result, "retakes", None) or []
    suggested = getattr(result, "suggested", None) or []
    if retakes:
        _plan_course_table("Buộc học lại (retakes)", retakes, retake=True)
    if retakes or suggested:
        total = sum(_f(c.get("credits")) or 0.0 for c in retakes + suggested)
        max_tc = getattr(result, "max_tc", None)
        footer = f"Tổng TC: {_fmt(float(total))}"
        footer += f" / max {_fmt(_f(max_tc))}" if max_tc is not None else ""
        console.print(f"[bold]{footer}[/bold]")
    _khoi_bars(getattr(result, "khối_progress", None) or [])
    if getattr(result, "off_round", False):
        _muted("(không có lớp mở trong đợt này — kế hoạch chỉ dựa trên CTĐT)")


def _format_vnd(amount) -> str:
    """1_140_000 → "1.140.000" (Vietnamese thousand separator)."""
    return f"{round(float(amount or 0)):,}".replace(",", ".")


def render_fee(fee: dict | None) -> None:
    """Tuition estimate block (fee.estimate output): flat fee, resulting
    total for the planned TC, plus the below-quota discount hint."""
    if not fee:
        return
    plan_tc = _fmt(fee.get("planned_tc"))
    total = _format_vnd(fee.get("total"))
    flat = _format_vnd(fee.get("flat_fee"))
    over_tc = fee.get("over_quota_tc") or 0.0
    over_fee = _format_vnd(fee.get("over_quota_fee"))
    if over_tc > 0:
        note = f"vượt định mức {_fmt(over_tc)} TC (+{over_fee} VNĐ)"
    else:
        pct = fee.get("discount_pct") or 0.0
        note = f"giảm {int(pct * 100)}%" if pct else "trong định mức"
    console.print(
        f"Học phí dự kiến ([bold]{fee['program']}[/bold]): "
        f"trọn gói {flat} VNĐ/HK · {plan_tc} TC ({note}) — [bold]{total} VNĐ[/bold]"
    )
    if (fee.get("planned_tc") or 0.0) <= 12.0:
        console.print(
            "[dim]Ưu đãi Bảng 1.2 (đăng ký dưới định mức): "
            "≤12 TC −15% · ≤9 TC −30% · ≤6 TC −45%.[/dim]"
        )


def render_plan_analysis(result: Any) -> None:
    """Full planning readout: trend + completion + khối + health + timeline.

    Kept separate from render_plan (the suggested-course table) so callers can
    show the concise plan or the analysis view. Every section is a pure
    projection of already-fetched data; nothing here re-fetches."""
    nxt = getattr(result, "next_semester", "") or "HK tới"
    console.print(Panel(_trend_line(getattr(result, "gpa", None)),
                        title=f"Phân tích — {nxt}"))
    _completion_block(getattr(result, "completion", None))
    render_gpa_trend(getattr(result, "gpa", None))
    render_khoi_compliance(getattr(result, "khoi", None) or [])
    render_grade_health(getattr(result, "health", None))
    render_fee(getattr(result, "fee", None))
    timeline = getattr(result, "timeline", None) or {}
    if timeline:
        at_max = _fmt(timeline.get("at_max"))
        at_pace = _fmt(timeline.get("at_pace"))
        avg = timeline.get("avg_credits_per_sem")
        note = f" (TB {_fmt(avg)} TC/HK)" if avg else ""
        console.print(
            f"[bold]Thời gian còn lại: {at_max} HK[/bold] ở mức tối đa "
            f"({_fmt(getattr(result, 'max_tc', None))} TC) · "
            f"[bold]{at_pace} HK[/bold] ở nhịp hiện tại{note}."
        )