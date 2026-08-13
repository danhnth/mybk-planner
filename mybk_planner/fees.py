"""Tuition estimation (pure data + math, no API).

Rates from the HCMUT fee notice 2026-2027:
- §I.2.b: định mức = 18 TC/HK for every program (quota).
- §I.2.f Bảng 1.2: flat-fee discounts when registering below quota:
  ≤12 TC → −15%, ≤9 TC → −30%, ≤6 TC → −45%.
- §III: per-chương-trình khóa semester flat fee + per-credit price;
  credits above the quota (vượt định mức) are billed at the per-credit rate.

Program code matching is prefix-based (profile.curriculum.code, e.g.
"DH_DHNB_MT_KHM_2023" → CTNB/CTHNB khóa 2023-24).
"""

from __future__ import annotations

QUOTA_TC = 18.0  # §I.2.b

# program-code prefix → (semester flat fee, per-credit price, label)
# Rates for khóa 2023-24 (the live-tested cohort).
FEE_PLANS: dict = {
    "DH_CQ": (15_750_000, 940_000, "CQ tiêu chuẩn"),
    "DH_DHNB": (30_000_000, 1_140_000, "CTNB/CTHNB khóa 2023-24"),
    "DH_CTTA": (40_000_000, 2_480_000, "CTTA/CTTT/CTQT khóa 2023-24"),
}

# Bảng 1.2 tiers: (max TC, discount), sorted by most-favorable first.
DISCOUNT_TIERS: tuple[tuple[float, float], ...] = (
    (6.0, 0.45), (9.0, 0.30), (12.0, 0.15),
)


def fee_plan(program_code: str) -> tuple[int, int, str] | None:
    code = str(program_code or "").upper()
    for prefix in sorted(FEE_PLANS, key=len, reverse=True):
        if code.startswith(prefix):
            return FEE_PLANS[prefix]
    return None


def discount_for_tc(tc: float) -> float:
    """Largest Bảng 1.2 discount applicable to a below-quota load."""
    for max_tc, pct in DISCOUNT_TIERS:
        if tc <= max_tc:
            return pct
    return 0.0


def estimate(program_code: str, planned_tc: float) -> dict | None:
    """Fee breakdown for a semester with ``planned_tc`` credits.

    Returns None when the program is not in the table (unknown code) or when
    ``planned_tc`` is empty/zero (no plan yet). ``total`` =
    flat fee (minus the below-quota discount) plus any vượt-định-mức credits.
    """
    plan = fee_plan(program_code)
    if plan is None:
        return None
    flat, per_credit, label = plan
    tc = max(0.0, float(planned_tc or 0.0))
    if tc <= 0.0:
        return None
    over_tc = max(0.0, tc - QUOTA_TC)
    if over_tc > 0.0:
        discount = 0.0
        over_fee = round(over_tc * per_credit)
        total = flat + over_fee
    else:
        discount = discount_for_tc(tc)
        over_fee = 0
        total = round(flat * (1 - discount))
    return {
        "program": label,
        "flat_fee": flat,
        "per_credit": per_credit,
        "quota": QUOTA_TC,
        "planned_tc": round(tc, 2),
        "discount_pct": discount,
        "over_quota_tc": round(over_tc, 2),
        "over_quota_fee": over_fee,
        "total": total,
    }