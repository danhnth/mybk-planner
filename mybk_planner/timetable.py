"""Thời khóa biểu (TKB) + lịch thi fetchers.

NOTE on the exams endpoint: `thoi-khoa-bieu/lich-thi-sinh-vien/v1` accepts any
masv as a plain parameter. This tool is designed for YOUR OWN account only —
do not use it on other students' data.
"""

from __future__ import annotations

from typing import Any

from .api import MyBK


def schedule(api: MyBK, student_id: str, semester_year: str = "") -> Any:
    """GET /api/v1/student/schedule?studentId=..&semesterYear=..&null

    semesterYear: YYYYk semester code, e.g. "20252" (or blank for current)."""
    return api.get(
        "v1/student/schedule",
        params={"studentId": student_id, "semesterYear": semester_year},
    )


def exams(api: MyBK, mssv: str, namhoc: str, hocky: str) -> Any:
    """GET /api/thoi-khoa-bieu/lich-thi-sinh-vien/v1?masv=&namhoc=&hocky=&null

    namhoc numeric year like "2025" (server rejects "2025-2026"), hocky like "2"."""
    return api.get(
        "thoi-khoa-bieu/lich-thi-sinh-vien/v1",
        params={"masv": mssv, "namhoc": namhoc, "hocky": hocky},
    )