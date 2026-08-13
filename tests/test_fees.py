"""Offline unit tests for mybk_planner.fees (pure rate tables + math).

Rates from the HCMUT 2026-27 fee notice:
- quota = 18 TC/HK (§I.2.b)
- below-quota discounts (§I.2.f Bảng 1.2): ≤6 → 45%, ≤9 → 30%, ≤12 → 15%
- CTNB/CTHNB khóa 2023-24: flat 30_000_000, per-credit 1_140_000
"""

from mybk_planner import fees

CTNB = "DH_DHNB_MT_KHM_2023"


class TestFeePlan:
    def test_ctnb_prefix_match(self):
        plan = fees.fee_plan(CTNB)
        assert plan == (30_000_000, 1_140_000, "CTNB/CTHNB khóa 2023-24")

    def test_cq_prefix_match(self):
        plan = fees.fee_plan("DH_CQ_K19")
        assert plan == (15_750_000, 940_000, "CQ tiêu chuẩn")

    def test_ctta_prefix_match(self):
        plan = fees.fee_plan("DH_CTTA_XYZ")
        assert plan == (40_000_000, 2_480_000, "CTTA/CTTT/CTQT khóa 2023-24")

    def test_matching_is_case_insensitive(self):
        assert fees.fee_plan("dh_dhnb_mt_khm_2023") == fees.fee_plan(CTNB)
        assert fees.fee_plan("Dh_Cq_K19") == fees.fee_plan("DH_CQ_K19")

    def test_unknown_prefix_returns_none(self):
        assert fees.fee_plan("XYZ_123") is None

    def test_empty_and_none_return_none(self):
        assert fees.fee_plan("") is None
        assert fees.fee_plan(None) is None


class TestDiscountForTc:
    def test_tier_boundaries(self):
        assert fees.discount_for_tc(6) == 0.45
        assert fees.discount_for_tc(9) == 0.30
        assert fees.discount_for_tc(12) == 0.15

    def test_inside_tiers(self):
        assert fees.discount_for_tc(1) == 0.45
        assert fees.discount_for_tc(7) == 0.30
        assert fees.discount_for_tc(10) == 0.15

    def test_above_tiers_no_discount(self):
        assert fees.discount_for_tc(13) == 0.0
        assert fees.discount_for_tc(18) == 0.0
        assert fees.discount_for_tc(25) == 0.0


class TestEstimate:
    def test_unknown_program_returns_none(self):
        assert fees.estimate("XYZ_123", 10) is None

    def test_non_positive_tc_returns_none(self):
        assert fees.estimate(CTNB, 0) is None
        assert fees.estimate(CTNB, -5) is None

    def test_within_quota_pays_flat_no_discount(self):
        result = fees.estimate(CTNB, 17)
        assert result["total"] == 30_000_000
        assert result["discount_pct"] == 0.0
        assert result["over_quota_tc"] == 0.0
        assert result["over_quota_fee"] == 0
        assert result["flat_fee"] == 30_000_000
        assert result["per_credit"] == 1_140_000
        assert result["quota"] == 18.0
        assert result["planned_tc"] == 17.0
        assert result["program"] == "CTNB/CTHNB khóa 2023-24"

    def test_exactly_at_quota_pays_flat(self):
        assert fees.estimate(CTNB, 18)["total"] == 30_000_000

    def test_below_quota_discount(self):
        result = fees.estimate(CTNB, 11)
        assert result["discount_pct"] == 0.15
        assert result["total"] == 25_500_000  # round(30_000_000 * 0.85)

    def test_deepest_discount_tier(self):
        result = fees.estimate(CTNB, 6)
        assert result["discount_pct"] == 0.45
        assert result["total"] == 16_500_000  # round(30_000_000 * 0.55)

    def test_over_quota_bills_per_credit(self):
        result = fees.estimate(CTNB, 20)
        assert result["discount_pct"] == 0.0
        assert result["over_quota_tc"] == 2.0
        assert result["over_quota_fee"] == 2_280_000
        assert result["total"] == 32_280_000  # 30_000_000 + 2 * 1_140_000

    def test_cq_plan_numbers(self):
        result = fees.estimate("DH_CQ_K19", 18)
        assert result["total"] == 15_750_000
        over = fees.estimate("DH_CQ_K19", 19)
        assert over["total"] == 15_750_000 + 940_000
        assert over["over_quota_tc"] == 1.0
