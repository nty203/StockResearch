"""Tests for US filters (us01–us20)."""
import pytest
from src.screening.filters_us import apply_us_filters, USFilterResult


@pytest.fixture
def passing_us_stock():
    """Mock US stock that passes all mandatory filters."""
    return {
        "ticker": "ACME",
        "market_cap": 2_000_000_000,   # $2B — passes $500M
        "avg_daily_value": 10_000_000, # $10M — passes $5M
        "revenue_ttm": 500_000_000,    # $500M
        "revenue_prev": 400_000_000,   # 25% growth — passes 15%
        "revenue_2y_ago": 300_000_000,
        "gross_margin": 55.0,          # passes 40%
        "debt_equity": 80.0,           # passes 300%
        "op_margin": 20.0,
        "op_margin_prev": 15.0,
        "roic": 25.0,
        "fcf": 50_000_000,
        "institutional_ownership_pct": 40.0,
        "rs_score": 80,
        "price": 100.0,
        "price_52w_high": 110.0,
        "ps_ratio": 8.0,
    }


@pytest.fixture
def failing_gross_margin():
    """Stock that fails gross_margin filter."""
    return {
        "ticker": "FAIL1",
        "market_cap": 2_000_000_000,
        "avg_daily_value": 10_000_000,
        "revenue_ttm": 500_000_000,
        "revenue_prev": 400_000_000,
        "gross_margin": 25.0,  # < 40% — FAIL
        "debt_equity": 80.0,
    }


class TestMandatoryFilters:
    def test_passes_all_mandatory(self, passing_us_stock):
        result = apply_us_filters(passing_us_stock)
        assert result.passed is True

    def test_fails_market_cap(self):
        stock = {
            "ticker": "SMALL",
            "market_cap": 100_000_000,  # $100M < $500M
            "avg_daily_value": 10_000_000,
            "revenue_ttm": 500_000_000,
            "revenue_prev": 400_000_000,
            "gross_margin": 55.0,
            "debt_equity": 80.0,
        }
        result = apply_us_filters(stock)
        assert result.passed is False
        assert "us01_market_cap" in result.failed_filters

    def test_fails_daily_value(self):
        stock = {
            "ticker": "ILLIQ",
            "market_cap": 2_000_000_000,
            "avg_daily_value": 1_000_000,  # $1M < $5M
            "revenue_ttm": 500_000_000,
            "revenue_prev": 400_000_000,
            "gross_margin": 55.0,
            "debt_equity": 80.0,
        }
        result = apply_us_filters(stock)
        assert result.passed is False
        assert "us02_daily_value" in result.failed_filters

    def test_fails_revenue_growth(self):
        stock = {
            "ticker": "SLOW",
            "market_cap": 2_000_000_000,
            "avg_daily_value": 10_000_000,
            "revenue_ttm": 400_000_000,
            "revenue_prev": 400_000_000,  # 0% growth
            "gross_margin": 55.0,
            "debt_equity": 80.0,
        }
        result = apply_us_filters(stock)
        assert result.passed is False
        assert "us03_revenue_growth" in result.failed_filters

    def test_fails_gross_margin(self, failing_gross_margin):
        result = apply_us_filters(failing_gross_margin)
        assert result.passed is False
        assert "us08_gross_margin" in result.failed_filters

    def test_fails_debt_equity(self):
        stock = {
            "ticker": "DEBT",
            "market_cap": 2_000_000_000,
            "avg_daily_value": 10_000_000,
            "revenue_ttm": 500_000_000,
            "revenue_prev": 400_000_000,
            "gross_margin": 55.0,
            "debt_equity": 400.0,  # > 300%
        }
        result = apply_us_filters(stock)
        assert result.passed is False
        assert "us09_debt_equity" in result.failed_filters

    def test_null_market_cap_fails(self):
        result = apply_us_filters({"ticker": "NULL"})
        assert result.passed is False
        assert "us01_market_cap" in result.failed_filters


class TestScoringFilters:
    def test_roic_above_20_scores(self, passing_us_stock):
        result = apply_us_filters(passing_us_stock)
        assert result.scores_by_filter.get("us06_roic", 0) > 0

    def test_roic_below_20_no_score(self, passing_us_stock):
        passing_us_stock["roic"] = 15.0
        result = apply_us_filters(passing_us_stock)
        assert "us06_roic" not in result.scores_by_filter

    def test_rs_score_above_70(self, passing_us_stock):
        result = apply_us_filters(passing_us_stock)
        assert result.scores_by_filter.get("us11_rs", 0) > 0

    def test_rs_score_below_70_no_score(self, passing_us_stock):
        passing_us_stock["rs_score"] = 60
        result = apply_us_filters(passing_us_stock)
        assert "us11_rs" not in result.scores_by_filter

    def test_near_52w_high_scores_momentum(self, passing_us_stock):
        # price=100, high=110 → 9% from high → within 20%
        result = apply_us_filters(passing_us_stock)
        assert result.scores_by_filter.get("us12_momentum", 0) > 0

    def test_far_from_52w_high_no_momentum(self, passing_us_stock):
        passing_us_stock["price"] = 70.0  # 36% from high — outside 20%
        result = apply_us_filters(passing_us_stock)
        assert "us12_momentum" not in result.scores_by_filter

    def test_ps_below_20_scores_value(self, passing_us_stock):
        result = apply_us_filters(passing_us_stock)
        assert result.scores_by_filter.get("us15_ps", 0) > 0

    def test_ps_above_20_no_value(self, passing_us_stock):
        passing_us_stock["ps_ratio"] = 25.0
        result = apply_us_filters(passing_us_stock)
        assert "us15_ps" not in result.scores_by_filter

    def test_institutional_above_30_scores(self, passing_us_stock):
        result = apply_us_filters(passing_us_stock)
        assert result.scores_by_filter.get("us10_institutional", 0) > 0

    def test_revenue_acceleration_scores(self, passing_us_stock):
        # current growth 25%, prior growth 33% → no accel
        result = apply_us_filters(passing_us_stock)
        # 500/400 = 25%, 400/300 = 33% — no accel (current < prior)
        assert "us04_accel" not in result.scores_by_filter

    def test_revenue_acceleration_positive(self, passing_us_stock):
        passing_us_stock["revenue_2y_ago"] = 380_000_000  # prior: 400/380=5.3% < current 25%
        result = apply_us_filters(passing_us_stock)
        assert result.scores_by_filter.get("us04_accel", 0) > 0

    def test_score_is_float(self, passing_us_stock):
        result = apply_us_filters(passing_us_stock)
        assert isinstance(result.score, float)

    def test_result_type(self, passing_us_stock):
        result = apply_us_filters(passing_us_stock)
        assert isinstance(result, USFilterResult)

    def test_settings_override(self, passing_us_stock):
        # Raise gross margin threshold above the stock's value
        settings = {"us_min_gross_margin": 60.0}
        result = apply_us_filters(passing_us_stock, settings)
        assert result.passed is False
        assert "us08_gross_margin" in result.failed_filters
