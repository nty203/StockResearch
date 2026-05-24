"""Tests for Piotroski / Sloan / Novy-Marx quality metrics (DART cumulative-aware)."""
import pytest
from src.hundredx.quality_metrics import (
    compute_gp_to_assets,
    compute_accruals_ratio,
    compute_piotroski_f_score,
    ttm_from_cumulative,
)


def _record(fq, revenue=100, op_income=10, net_income=8, cfo=12,
            gross_profit=30, total_assets=1000, total_equity=600,
            total_liab=400, shares_out=1_000_000):
    return dict(fq=fq, revenue=revenue, op_income=op_income,
                net_income=net_income, cfo=cfo, gross_profit=gross_profit,
                total_assets=total_assets, total_equity=total_equity,
                total_liab=total_liab, shares_out=shares_out)


class TestTTMCumulative:
    def test_q4_returns_annual(self):
        # Latest Q4 = annual cumulative; TTM = Q4 value directly.
        recs = [_record("2025Q4", revenue=400)]
        assert ttm_from_cumulative(recs, "revenue") == 400

    def test_q3_rolling(self):
        # TTM at 2025Q3 = Q4_2024 + Q3_2025 - Q3_2024 = 400 + 300 - 200 = 500
        recs = [
            _record("2025Q3", revenue=300),
            _record("2025Q2", revenue=200),
            _record("2025Q1", revenue=100),
            _record("2024Q4", revenue=400),
            _record("2024Q3", revenue=200),
        ]
        assert ttm_from_cumulative(recs, "revenue") == 500


class TestGPToAssets:
    def test_basic(self):
        # Latest Q4 with gp=120 (annual cumulative), assets=1000 → 0.12
        recs = [_record("2025Q4", gross_profit=120, total_assets=1000)]
        assert compute_gp_to_assets(recs) == 0.12

    def test_empty(self):
        assert compute_gp_to_assets([]) is None

    def test_no_assets(self):
        recs = [_record("2025Q4", total_assets=None)]
        assert compute_gp_to_assets(recs) is None


class TestAccrualsRatio:
    def test_clean_earnings(self):
        # Annual NI=8, CFO=12 (current and prior year) → accruals < 0
        recs = [
            _record("2025Q4", net_income=8, cfo=12, total_assets=1000),
            _record("2024Q4", net_income=8, cfo=12, total_assets=1000),
        ]
        result = compute_accruals_ratio(recs)
        assert result is not None and result < 0

    def test_high_accruals(self):
        # 2025 annual NI=20, CFO=5 → accruals > 0
        recs = [
            _record("2025Q4", net_income=20, cfo=5, total_assets=1000),
            _record("2024Q4", net_income=10, cfo=10, total_assets=1000),
        ]
        result = compute_accruals_ratio(recs)
        assert result is not None and result > 0


class TestFScore:
    def test_strong_score(self):
        # All annual metrics improving year-over-year.
        recs = [
            _record("2025Q4", revenue=480, op_income=60, net_income=60,
                    cfo=80, gross_profit=160, total_assets=1100,
                    total_liab=400, shares_out=1_000_000),
            _record("2024Q4", revenue=400, op_income=32, net_income=32,
                    cfo=40, gross_profit=100, total_assets=1000,
                    total_liab=450, shares_out=1_000_000),
        ]
        # Need 5+ quarters for F-Score; pad with Q3 entries.
        recs.extend([
            _record("2025Q3", revenue=360, op_income=45, net_income=45, cfo=60,
                    gross_profit=120, total_assets=1080, total_liab=410),
            _record("2024Q3", revenue=300, op_income=24, net_income=24, cfo=30,
                    gross_profit=75, total_assets=990, total_liab=455),
            _record("2023Q4", revenue=320, op_income=20, net_income=20, cfo=25,
                    gross_profit=80, total_assets=950, total_liab=470),
        ])
        score = compute_piotroski_f_score(recs)
        assert score is not None and score >= 5

    def test_insufficient_data(self):
        recs = [_record(f"2025Q{q}") for q in (4, 3)]
        assert compute_piotroski_f_score(recs) is None
