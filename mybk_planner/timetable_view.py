"""Rich renderers for schedule & exams, paired with timetable.py's data feed.

Timetable data is structurally distinct from academic summaries (nested
subject/classGroup/room/employee dicts; a legacy headers/data wrapper; HCMUT
day codes 2..8 and "07g00"-style start times), so its presentation lives apart
from ui.py's core renderers. Pure presentation: consumes an already-fetched
payload, prints via ui.console, no API calls.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from rich.table import Table

from .ui import _f, _fmt, _muted, console


def _day_name(v: Any) -> str:
    """Map HCMUT day codes (2=Monday..7=Saturday, 8=Sunday) to Vietnamese.

    Day 0 marks records without a fixed slot (internships, student activities,
    labs announced later) — render as an em dash, not "0".
    """
    names = {2: "Thứ 2", 3: "Thứ 3", 4: "Thứ 4", 5: "Thứ 5", 6: "Thứ 6", 7: "Thứ 7", 8: "CN"}
    num = _f(v)
    if num is not None and int(num) in names:
        return names[int(num)]
    return "—"


def _date_vn(v: Any) -> str:
    """'2026-06-02' -> '02/06/2026'; non-ISO input falls back to raw text."""
    s = str(v or "")
    try:
        return date.fromisoformat(s).strftime("%d/%m/%Y")
    except ValueError:
        return _fmt(v)


def _exams_payload_rows(payload: Any) -> list[dict]:
    """Exams feed wraps rows in {"headers":…, "data":[…]}; schedule returns a bare list."""
    rows = payload.get("data") if isinstance(payload, dict) else payload
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def _schedule_rows(payload: Any) -> list[dict]:
    """The /app feed returns one record per teacher-session, so one class can
    appear twice (e.g. GE1013 shows twice with different internal ids but the
    same course/group/room/day/time). Dedupe on the rendered fields, first-wins."""
    raw = payload if isinstance(payload, list) else []
    seen, out = set(), []
    for r in raw:
        if not isinstance(r, dict):
            continue
        subj = r.get("subject") or {}
        grp = r.get("subjectClassGroup") or {}
        room = r.get("room") or {}
        emp = r.get("employee") or {}
        key = (subj.get("code"), grp.get("classGroup"), room.get("code"),
               r.get("dayOfWeek"), r.get("startTime"), r.get("endTime"),
               emp.get("lastName"), emp.get("firstName"))
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def render_schedule(payload: Any) -> None:
    rows = _schedule_rows(payload)
    if not rows:
        _muted("— không có dữ liệu (ngoài đợt?).")
        return
    table = Table(title="Thời khóa biểu", header_style="bold cyan")
    for col in ("Thứ", "Giờ", "Mã MH", "Tên môn", "Nhóm", "Phòng", "GV"):
        table.add_column(col)
    for r in rows:
        subj = r.get("subject") or {}
        grp = r.get("subjectClassGroup") or {}
        room = r.get("room") or {}
        emp = r.get("employee") or {}
        table.add_row(
            _day_name(r.get("dayOfWeek")),
            f"{_fmt(r.get('startTime'))}–{_fmt(r.get('endTime'))}",
            _fmt(subj.get("code")),
            _fmt(subj.get("nameVi")),
            _fmt(grp.get("classGroup")),
            _fmt(room.get("code")),
            _fmt(" ".join(p for p in (emp.get("lastName"), emp.get("firstName")) if p)),
        )
    console.print(table)


def render_exams(payload: Any) -> None:
    rows = _exams_payload_rows(payload)
    if not rows:
        _muted("— không có dữ liệu (ngoài đợt?).")
        return
    table = Table(title="Lịch thi", header_style="bold cyan")
    for col in ("Ngày", "Thứ", "Giờ", "Loại", "Mã MH", "Tên môn", "Phòng"):
        table.add_column(col)
    for r in rows:
        gio = str(r.get("GIOBD") or "").replace("g", ":") or "—"  # "07g00" -> "07:00"
        table.add_row(
            _date_vn(r.get("NGAYTHI")), _day_name(r.get("THU")), gio,
            _fmt(r.get("LOAITHI")), _fmt(r.get("MAMONHOC")),
            _fmt(r.get("TENMONHOC")), _fmt(r.get("MAPHONG")),
        )
    console.print(table)
