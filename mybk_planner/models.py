"""Shared dataclasses for planner consumption.

The live API returns dicts whose exact field names vary between the
`share/ket-qua-hoc-tap/*` and `sinh-vien/*` families. `GradeRecord.normalize`
is a tolerant alias-picker so downstream planner logic works regardless of
which family a row came from; the original dict is always kept in `.raw`.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class GradeRecord:
    subject_code: str | None = None
    subject_name: str | None = None
    credits: float | None = None
    score_10: float | None = None
    score_4: float | None = None
    letter: str | None = None
    semester: str | None = None
    status: str | None = None  # Dat / Khong dat / etc.
    raw: dict = field(default_factory=dict)

    @classmethod
    def normalize(cls, row: dict) -> GradeRecord:
        def pick(*keys):
            return next((row[k] for k in keys if row.get(k) is not None), None)

        def as_float(v):
            if v is None or v == "":
                return None
            try:
                return float(v)
            except (TypeError, ValueError):
                return None

        return cls(
            subject_code=pick("maMonHoc", "mamonhoc", "maMH", "ma_mh", "maMon", "mamh", "subjectCode"),
            subject_name=pick("tenMonHoc", "tenmonhoc", "tenMH", "ten_mh", "tenmhvn", "subjectName"),
            credits=as_float(pick("soTinChi", "sotinchi", "so_tin_chi", "tinChi", "tc", "credits")),
            score_10=as_float(pick("diem10", "diemThang10", "diem_thang_10", "diemSo", "diemso", "diemcu", "score10")),
            score_4=as_float(pick("diem4", "diemThang4", "diem_thang_4", "score4")),
            letter=pick("diemChu", "diem_chu", "diemchu", "letter"),
            semester=pick("hocKy", "hoc_ky", "maHocKy", "mahk", "semester", "kyHoc"),
            status=pick("trangThai", "trang_thai", "status", "diemTrangThai", "tinhtrangdiem"),
            raw=row,
        )

    @property
    def passed(self) -> bool:
        """Pass = diemDat=="1" (authoritative) else grade heuristics with the
        HCMUT D>=4.0 threshold (a D is a pass). diemDat=="0" => failed even
        when a later heuristics pass; absent diemDat falls back to score/letter."""
        dat = self.raw.get("diemDat") or self.raw.get("diemdat")
        if dat in ("1", 1, True, "true"):
            return True
        if dat in ("0", 0):
            return False
        if self.letter and self.letter.strip().upper() in ("F", "0", "R", "X"):
            return False
        if self.score_10 is not None and self.score_10 < 4.0:
            return False
        if self.score_4 is not None and self.score_4 < 1.0:
            return False
        status = (self.status or "").lower()
        return not ("khong dat" in status or "không đạt" in status or "rot" in status)


@dataclass
class CtdtCourse:
    code: str
    name: str
    credits: float | None = None
    kind: str | None = None  # BB (bắt buộc) / TC (tự chọn)
    prerequisite_codes: list = field(default_factory=list)
    suggested_semester: str | None = None
    raw: dict = field(default_factory=dict)


@dataclass
class ClassGroup:
    """One open class (nhóm lớp) for a course — the 'lớp mở' record."""

    course_code: str
    course_name: str
    group: str | None = None
    teacher: str | None = None
    slots: int | None = None
    enrolled: int | None = None
    schedule: str | None = None  # human-readable TKB string from the raw payload
    raw: dict = field(default_factory=dict)