"""Modern /app sinh-vien/* registration listing — read-only.

The /app SPA drives registration through the `sinh-vien/*` JSON API family
(verified live 2026-08-14 under an own student account: 200 + standard
{code,msg,data,sign} envelope; `data` empty off-season until a đợt opens):

    GET sinh-vien/danh-sach-dot-dang-ky/RUTMON/621/v1
        -> current đợt(s); data[0].{id, nbr, text, hockytkb, ngaybatdau,
           ngayketthuc, ghichu}
    GET sinh-vien/thoi-khoa-bieu/{hockytkb}/RUTMON/v1
        -> open/withdrawable classes {mamonhoc, tenmonhoc, nhomlop, thoihan}
    GET sinh-vien/danh-sach-phieu-dang-ky/621/regnew/v1   (pending tickets)
    GET sinh-vien/danh-sach-phieu-dang-ky/621/finished/v1 (processed tickets)
    GET sinh-vien/khao-thi/dot-dang-ky-hoan-thi/v1?hocky=<ma>   (defer-exam đợt)
    GET sinh-vien/khao-thi/danh-sach-mon-hoc-du-thi/v1?dot=<ma> (defer-exam rows)
    GET share/dic/nam-hoc-hoc-ky/hoan_thi/vi/v1                 (semester dict)
    GET sinh-vien/thong-tin-nguoi-dang-ky/v1                    (own profile)

WRITE endpoints discovered in the same SPA bundles are deliberately NOT
exposed by this module:
`sinh-vien/tao-phieu-dang-ky/v1` (POST), `sinh-vien/huy-phieu-dang-ky/{id}/v1`
(DELETE), `sinh-vien/khao-thi/cap-nhat-thong-tin-dang-ky-du-thi/v1` (POST),
`sinh-vien/khao-thi/cap-nhat-minh-chung-hoan-thi/v1` (POST).
"""

from __future__ import annotations

from typing import Any

from .api import MyBK

RUTMON_LOAI_DANG_KY_ID = "621"  # loaiDangKyId for "Đăng ký rút môn học" feed


class DkmhError(RuntimeError):
    pass


def reg_dots(api: MyBK, reg_type: str = "RUTMON", loai_dang_ky_id: str = RUTMON_LOAI_DANG_KY_ID) -> Any:
    """Current registration đợt(s) for a feed type. GET sinh-vien/danh-sach-dot-dang-ky/<TYPE>/<LID>/v1."""
    return api.get(f"sinh-vien/danh-sach-dot-dang-ky/{reg_type}/{loai_dang_ky_id}/v1")


def reg_open_classes(api: MyBK, hockytkb: str, reg_type: str = "RUTMON") -> Any:
    """Open/withdrawable classes for a semester (thời khóa biểu feed)."""
    return api.get(f"sinh-vien/thoi-khoa-bieu/{hockytkb}/{reg_type}/v1")


def reg_my_tickets(api: MyBK, loai_dang_ky_id: str = RUTMON_LOAI_DANG_KY_ID) -> dict:
    """Own registration tickets: {pending, finished} via the two GET feeds."""
    return {
        "pending": api.get(f"sinh-vien/danh-sach-phieu-dang-ky/{loai_dang_ky_id}/regnew/v1"),
        "finished": api.get(f"sinh-vien/danh-sach-phieu-dang-ky/{loai_dang_ky_id}/finished/v1"),
    }


def reg_defer_semesters(api: MyBK) -> Any:
    """Semester dictionary the defer-exam page feeds its dropdown from."""
    return api.get("share/dic/nam-hoc-hoc-ky/hoan_thi/vi/v1")


def reg_defer_dot(api: MyBK, hocky_ma: str) -> Any:
    """Đợt đăng ký hoãn thi for a semester code (e.g. 20253)."""
    return api.get("sinh-vien/khao-thi/dot-dang-ky-hoan-thi/v1", params={"hocky": hocky_ma})


def reg_defer_exam_courses(api: MyBK, dot_ma: str) -> Any:
    """Exam rows in a hoãn-thi đợt: {maHocKyNhomLop, maMonHoc, tenMonHoc, maNhom, maTo, ngayThi, tinhTrang, ...}."""
    return api.get("sinh-vien/khao-thi/danh-sach-mon-hoc-du-thi/v1", params={"dot": dot_ma})


def reg_own_profile(api: MyBK) -> Any:
    """Own registrant profile (thong-tin-nguoi-dang-ky)."""
    return api.get("sinh-vien/thong-tin-nguoi-dang-ky/v1")
