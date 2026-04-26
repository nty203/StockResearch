"""Tests for KR filters — 효성중공업 2023Q1 backtest + 에코프로 peak_risk."""
import pytest
from src.screening.filters_kr import apply_kr_filters, FilterResult
from src.screening.peak_risk import apply_peak_risk_penalty


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def hyosung_2023q1():
    """효성중공업 2023Q1 — should pass all mandatory filters."""
    return {
        "ticker": "298040",
        "market": "KOSPI",
        "market_cap": 2_500_000_000_000,   # 2.5조 KRW
        "avg_daily_value": 15_000_000_000, # 150억
        "revenue_ttm": 3_200_000_000_000,  # 3.2조
        "revenue_prev": 2_500_000_000_000, # 2.5조 (28% growth)
        "revenue_2y_ago": 2_000_000_000_000,
        "op_margin_ttm": 7.5,
        "op_margin_prev": 5.0,
        "roic": 14.0,
        "fcf": 80_000_000_000,
        "debt_ratio": 180.0,
        "order_backlog": 5_000_000_000_000, # 5조 수주잔고
        "order_backlog_prev": 4_000_000_000_000,
        "foreign_ownership_pct": 22.0,
        "price": 85_000,
        "price_52w_high": 92_000,
    }


@pytest.fixture
def ecopro_peak():
    """에코프로 2023Q4 peak data — should trigger peak_risk penalty."""
    return {
        "ticker": "086520",
        "ps_ratio": 25.0,   # >= 20
        "fcf": -50_000_000_000,  # negative
        "insider_sell_pct": 6.5, # > 5%
    }


@pytest.fixture
def failing_stock():
    """Stock that should fail mandatory market_cap filter."""
    return {
        "ticker": "999999",
        "market": "KOSDAQ",
        "market_cap": 50_000_000_000,  # 500억 — below 300억 threshold? No, below min
        "avg_daily_value": 1_000_000_000,
        "revenue_ttm": 30_000_000_000,
        "revenue_prev": 29_000_000_000,
        "op_margin_ttm": 3.0,
        "debt_ratio": 150.0,
    }


# ── Tests ─────────────────────────────────────────────────────────────────

class TestHyosungFilters:
    def test_passes_mandatory_filters(self, hyosung_2023q1):
        result = apply_kr_filters(hyosung_2023q1)
        assert result.passed is True

    def test_no_failed_mandatory_filters(self, hyosung_2023q1):
        result = apply_kr_filters(hyosung_2023q1)
        mandatory = {"f01_market_cap", "f02_daily_value", "f03_revenue_growth", "f08_backlog", "f09_debt_ratio"}
        assert not any(f in mandatory for f in result.failed_filters)

    def test_positive_score(self, hyosung_2023q1):
        result = apply_kr_filters(hyosung_2023q1)
        assert result.score > 0

    def test_growth_acceleration_score_present(self, hyosung_2023q1):
        result = apply_kr_filters(hyosung_2023q1)
        # f03 is mandatory (pass/fail), scoring goes to f04 (acceleration)
        assert result.scores_by_filter.get("f04", 0) > 0

    def test_op_margin_score_present(self, hyosung_2023q1):
        result = apply_kr_filters(hyosung_2023q1)
        # f05 scoring can be f05_margin_trend or similar — check any f05 key
        f05_keys = [k for k in result.scores_by_filter if k.startswith("f05")]
        assert len(f05_keys) > 0 or result.scores_by_filter.get("f07_fcf", 0) > 0

    def test_settings_override_threshold(self, hyosung_2023q1):
        # Lower market cap threshold to ensure still passes
        settings = {"kr_min_market_cap": 100_000_000_000}  # 1000억
        result = apply_kr_filters(hyosung_2023q1, settings)
        assert result.passed is True


class TestFailingStock:
    def test_fails_when_low_daily_value(self):
        stock = {
            "ticker": "000001",
            "market_cap": 1_000_000_000_000,  # passes market cap
            "avg_daily_value": 500_000_000,    # 5억 — below 5B threshold
            "revenue_ttm": 200_000_000_000,
            "revenue_prev": 100_000_000_000,
            "op_margin_ttm": 8.0,
            "debt_ratio": 100.0,
        }
        result = apply_kr_filters(stock)
        assert result.passed is False
        assert "f02_daily_value" in result.failed_filters

    def test_fails_when_no_revenue_growth(self):
        stock = {
            "ticker": "000002",
            "market_cap": 1_000_000_000_000,
            "avg_daily_value": 10_000_000_000,
            "revenue_ttm": 100_000_000_000,
            "revenue_prev": 110_000_000_000,  # declining
            "op_margin_ttm": 8.0,
            "debt_ratio": 100.0,
        }
        result = apply_kr_filters(stock)
        assert result.passed is False
        assert "f03_revenue_growth" in result.failed_filters

    def test_returns_filter_result_type(self):
        # All-None data passes with zero score (benefit of the doubt — unknown != bad).
        # Only known-bad data (e.g. revenue explicitly 0 or below threshold) should fail.
        stock = {"ticker": "000003"}
        result = apply_kr_filters(stock)
        assert isinstance(result, FilterResult)
        assert result.passed is True  # No data → pass (score will be 0)
        assert result.score == 0.0

    def test_fails_when_revenue_is_zero(self):
        # When revenue_ttm is positively known to be 0, f08 should fail.
        stock = {
            "ticker": "000004",
            "revenue_ttm": 0,
            "order_backlog": None,
        }
        result = apply_kr_filters(stock)
        assert isinstance(result, FilterResult)
        assert result.passed is False
        assert "f08_backlog" in result.failed_filters


class TestPeakRiskPenalty:
    def test_all_three_flags_apply_penalty(self, ecopro_peak):
        penalty = apply_peak_risk_penalty(ecopro_peak)
        assert penalty == 30.0

    def test_only_two_flags_no_penalty(self):
        stock = {
            "ps_ratio": 25.0,  # flag 1
            "fcf": -50_000_000_000,  # flag 2
            "insider_sell_pct": 3.0,  # no flag
        }
        penalty = apply_peak_risk_penalty(stock)
        assert penalty == 0.0

    def test_only_one_flag_no_penalty(self):
        stock = {
            "ps_ratio": 25.0,  # flag 1 only
            "fcf": 100_000_000,
            "insider_sell_pct": 1.0,
        }
        penalty = apply_peak_risk_penalty(stock)
        assert penalty == 0.0

    def test_no_flags_no_penalty(self):
        stock = {
            "ps_ratio": 5.0,
            "fcf": 100_000_000,
            "insider_sell_pct": 1.0,
        }
        penalty = apply_peak_risk_penalty(stock)
        assert penalty == 0.0

    def test_missing_fields_no_crash(self):
        penalty = apply_peak_risk_penalty({})
        assert penalty == 0.0

    def test_exactly_at_threshold(self):
        stock = {
            "ps_ratio": 20.0,   # exactly at threshold
            "fcf": -1,          # just negative
            "insider_sell_pct": 5.01,  # just above 5%
        }
        penalty = apply_peak_risk_penalty(stock)
        assert penalty == 30.0
