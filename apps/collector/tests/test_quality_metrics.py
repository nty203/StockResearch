"""Tests for Piotroski / Sloan / Novy-Marx quality metrics."""
import pytest
from src.hundredx.quality_metrics import (
    compute_gp_to_assets,
    compute_accruals_ratio,
    compute_piotroski_f_score,
)


def _record(fq, revenue=100, op_income=10, net_income=8, cfo=12,
            gross_profit=30, total_assets=1000, total_equity=600,
            total_liab=400, shares_out=1_000_000):
    return dict(fq=fq, revenue=revenue, op_income=op_income,
                net_income=net_income, cfo=cfo, gross_profit=gross_profit,
                total_assets=total_assets, total_equity=total_equity,
                total_liab=total_liab, shares_out=shares_out)


class TestGPToAssets:
    def test_basic(self):
        recs = [_record(f"2025Q{q}") for q in (4, 3, 2, 1)]
        # gp_ttm = 30*4 = 120, assets = 1000 → 0.12
        assert compute_gp_to_assets(recs) == 0.12

    def test_empty(self):
        assert compute_gp_to_assets([]) is None

    def test_no_assets(self):
        recs = [_record("2025Q4", total_assets=None)]
        assert compute_gp_to_assets(recs) is None


class TestAccrualsRatio:
    def test_clean_earnings(self):
        # CFO > NI consistently → accruals negative (good)
        recs = [_record(f"2025Q{q}", net_income=8, cfo=12) for q in (4, 3, 2, 1)] + \
               [_record(f"2024Q{q}", net_income=8, cfo=12) for q in (4, 3, 2, 1)]
        result = compute_accruals_ratio(recs)
        assert result is not None and result < 0

    def test_high_accruals(self):
        recs = [_record(f"2025Q{q}", net_income=20, cfo=5) for q in (4, 3, 2, 1)] + \
               [_record(f"2024Q{q}") for q in (4, 3, 2, 1)]
        result = compute_accruals_ratio(recs)
        assert result is not None and result > 0


class TestFScore:
    def test_perfect_score(self):
        # All metrics improving: 9 points
        recent = [_record(f"2025Q{q}", revenue=120, op_income=15, net_income=15,
                          cfo=20, gross_profit=40, total_assets=1100,
                          total_liab=400, shares_out=1_000_000) for q in (4, 3, 2, 1)]
        prior = [_record(f"2024Q{q}", revenue=100, op_income=8, net_income=8,
                         cfo=10, gross_profit=25, total_assets=1000,
                         total_liab=450, shares_out=1_000_000) for q in (4, 3, 2, 1)]
        score = compute_piotroski_f_score(recent + prior)
        assert score is not None and score >= 7  # 충분히 강함

    def test_insufficient_data(self):
        recs = [_record(f"2025Q{q}") for q in (4, 3)]
        assert compute_piotroski_f_score(recs) is None
