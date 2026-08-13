"""Bảng điểm / GPA / CTĐT fetchers — endpoint map verified against the live portal.

All share/ket-qua-hoc-tap/* endpoints below were exercised with a live CAS
student session and are JWT-bound: the client-supplied student id is ignored,
the caller's own record is returned (SHA256 byte-identical responses across
own/bogus body values).

LIVE (200):
  POST share/ket-qua-hoc-tap/danh-sach-diem-hoc-ky-mon-hoc/v2   body=maSinhVien
  POST share/ket-qua-hoc-tap/thong-tin-mo-ta-bang-diem/v2      body=maSinhVien  (GPA summary)
  POST share/ket-qua-hoc-tap/danh-sach-mon-hoc-xet-tuong-duong/v2  body=maSinhVien
  POST share/ket-qua-hoc-tap/danh-sach-diem-mon-hoc-khac/v2    body=maSinhVien  (external grades)
  POST share/ket-qua-hoc-tap/thong-tin-tinh-trang-diem-thanh-phan-mon-hoc/v2 body=sinhVienId
  POST share/ket-qua-hoc-tap/danh-sach-mon-hoc-ngoai-/v2?tuychon=VIEW_CTDT_SINHVIEN body=mssv
  POST share/ket-qua-hoc-tap/cap-nhat-diem-trung-binh-tich-luy-hoc-ky-chung/v2 — JWT-bound
      recompute of the CALLER's GPA ("write" in name, returns "done"; safe, no damage)
  GET  v1/student/get-student-info       (JWT-bound own profile)

DECOMMISSIONED / DISABLED (do not rely on):
  share/ket-qua-hoc-tap/bang-diem-hoc-ky/v2, diem-trung-binh-tich-luy/v2  → 404
  share/ket-qua-hoc-tap/tai-danh-sach-mon-hoc-ctdt/v2                     → 500 "Tùy chọn chưa cài đặt"
"""

from __future__ import annotations

from typing import Any

from .api import MyBK
from .models import GradeRecord

GRADES_BY_SEMESTER = "share/ket-qua-hoc-tap/danh-sach-diem-hoc-ky-mon-hoc/v2"
TRANSCRIPT_SUMMARY = "share/ket-qua-hoc-tap/thong-tin-mo-ta-bang-diem/v2"
EQUIVALENT_COURSES = "share/ket-qua-hoc-tap/danh-sach-mon-hoc-xet-tuong-duong/v2"
EXTERNAL_GRADES = "share/ket-qua-hoc-tap/danh-sach-diem-mon-hoc-khac/v2"
PARTIAL_GRADES = "share/ket-qua-hoc-tap/thong-tin-tinh-trang-diem-thanh-phan-mon-hoc/v2"
OTHER_PROGRAM_GRADES = "share/ket-qua-hoc-tap/danh-sach-mon-hoc-ngoai-/v2"
RECOMPUTE_GPA = "share/ket-qua-hoc-tap/cap-nhat-diem-trung-binh-tich-luy-hoc-ky-chung/v2"
CTDT_COURSES = "share/ket-qua-hoc-tap/danh-sach-mon-hoc-ctdt/v2"


def get_student_info(api: MyBK) -> Any:
    """GET /api/v1/student/get-student-info — JWT-bound own profile."""
    return api.get("v1/student/get-student-info")


def xem_ket_qua_hoc_tap(api: MyBK, mssv: str) -> Any:
    """THE transcript+ GPA source (GET sinh-vien family, SE-Smart-Study-Space).
    Returns dict {diem: [rows with dtbtl/dtbhk/diemchu...], tinChiTichLuy:
    [per-semester {mahk, tbtlchunghe4, tbtlchunghe10, tinchi}]}. Rows and the
    per-semester array are keyed on the JWT subject — client mssv is a filter."""
    return api.get("sinh-vien/xem-ket-qua-hoc-tap/v2", params={"mssv": mssv})


def gpa_summary(api: MyBK, mssv: str) -> dict:
    """Latest cumulative GPA + credits from tinChiTichLuy (skip BL/99991 rows).
    Returns {gpa_4, gpa_10, credits} of the last REAL semester."""
    payload = xem_ket_qua_hoc_tap(api, mssv)
    rows = payload.get("tinChiTichLuy") or []
    real = [
        r for r in rows
        if str(r.get("mahk", "")).strip() not in ("", "BL", "99991")
        and r.get("tbtlchunghe4") not in (None, "", "--", "0")
    ]
    if not real:
        return {"gpa_4": None, "gpa_10": None, "credits": None, "rows": rows}
    last = real[-1]
    return {
        "gpa_4": _f(last.get("tbtlchunghe4")),
        "gpa_10": _f(last.get("tbtlchunghe10")),
        "credits": _f(last.get("tinchi")),
        "rows": real,
    }


def _f(v) -> Any:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _mssv_of(profile: Any, mssv: str | None = None) -> Any:
    """Body value: explicit mssv, else best guess from the profile dict."""
    if mssv:
        return mssv
    if isinstance(profile, dict):
        for k in ("maSinhVien", "mssv", "maSV", "studentId", "id"):
            v = profile.get(k)
            if v not in (None, "", 0):
                return v
    return None


def grades(api: MyBK, mssv: str | None = None, tuychon: str = "BANGDIEM_MONHOC") -> Any:
    """The transcript itself (all semesters' grades). JWT-bound to caller."""
    return api.post(GRADES_BY_SEMESTER, params={"tuychon": tuychon}, data=mssv if mssv else {})


def transcript_summary(api: MyBK, mssv: str | None = None) -> Any:
    """Transcript header block (masv/lớp/họ tên/học kỳ hiện tại).
    Requires tuychon=VIEWONLINE; the numbers live in xem_ket_qua_hoc_tap()."""
    return api.post(TRANSCRIPT_SUMMARY, params={"tuychon": "VIEWONLINE"}, data=mssv if mssv else {})


def partial_grades_status(api: MyBK, sinh_vien_id: Any) -> Any:
    """Điểm thành phần per môn (structural grades); body key is sinhVienId here."""
    return api.post(PARTIAL_GRADES, data=sinh_vien_id)


def equivalent_courses(api: MyBK, mssv: str) -> Any:
    """Điểm tương đương (khi có) — needs tuychon=VIEWONLINE (returns null if none)."""
    return api.post(EQUIVALENT_COURSES, params={"tuychon": "VIEWONLINE"}, data=mssv)


def external_courses(api: MyBK, mssv: str) -> Any:
    """Courses the planner should also consider (ĐC, thể dục...) — body mssv."""
    return api.post(OTHER_PROGRAM_GRADES, params={"tuychon": "VIEW_CTDT_SINHVIEN"}, data=mssv)


def external_grades(api: MyBK, mssv: str) -> Any:
    """Môn học khác (giáo dục thể chất…, Đạt/không) — needs tuychon=BANGDIEM."""
    return api.post(EXTERNAL_GRADES, params={"tuychon": "BANGDIEM"}, data=mssv)


def recompute_own_gpa(api: MyBK, mssv: str | None = None) -> Any:
    """Server-side GPA recompute for the CALLER's own record (JWT-bound).
    Returns {"code":"200","msg":"ok","data":"done"} — client id ignored."""
    return api.post(RECOMPUTE_GPA, params={"tuychon": "BANGDIEM"}, data={})


def ctdt_courses(api: MyBK, mssv: str | None = None) -> Any:
    """CTĐT course list. The download variant is server-disabled; this read
    variant's availability is UNCONFIRMED — the planner's master-plan should
    primarily use the offline CTĐT CSV seed, with this as a live cross-check."""
    return api.post(CTDT_COURSES, data=mssv if mssv else {})


def normalize_grade_rows(rows: Any) -> list[GradeRecord]:
    if not isinstance(rows, list):
        return []
    return [GradeRecord.normalize(r) for r in rows if isinstance(r, dict)]


def summarize_grades(records: list[GradeRecord]) -> dict:
    """Course-level status buckets: a retake pass makes the course passed and
    its old F row stops counting as failed (MT1003: F@20231 then D+@20233 →
    passed). Counts cover distinct course codes; rows keep full history."""
    passed = [r for r in records if r.passed]
    passed_codes = {r.subject_code for r in passed if r.subject_code}
    failed_by_code: dict = {}
    for r in records:
        code = r.subject_code
        if not code or code in passed_codes:
            continue
        prev = failed_by_code.get(code)
        if prev is None or (r.semester or "") >= (prev.semester or ""):
            failed_by_code[code] = r
    failed = sorted(failed_by_code.values(), key=lambda r: r.subject_code)
    low = [r for r in passed if (r.letter or "").strip().upper() in ("D", "D+")]
    scores = [r.score_10 for r in passed if r.score_10 is not None]
    return {
        "total": len(passed_codes) + len(failed),
        "passed": len(passed_codes),
        "failed": len(failed),
        "failed_records": failed,
        "improvable_D": len(low),
        "mean_score_10": round(sum(scores) / len(scores), 2) if scores else None,
    }