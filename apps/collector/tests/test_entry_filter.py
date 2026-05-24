"""Tests for trading.entry_filter -- 7-gate buy decision logic."""
import pytest
from src.hundredx.trading.entry_filter import check_entry, EntryDecision

CATEGORY = "수주재고_선행"  # 수주잔고_선행


def base_stock(overrides=None):
    """Minimal stock_data that passes all filters by default."""
    data = {
        "market": "KOSPI",
        "avg_daily_value_60d": 50_000_000_000,  # 500bn KRW -- well above 5m*100
        "close": 10_000,
        "ma20": 9_800,
        "ma60": 9_000,
        "ma200": 8_000,
        "kospi_close": 2_600,
        "kospi_ma200": 2_200,
        "min_60d_return": -0.08,  # -8%, above -15% threshold
    }
    if overrides:
        data.update(overrides)
    return data


def base_portfolio(overrides=None):
    ps = {
        "n_positions": 3,
        "max_positions": 15,
        f"category_weight_{CATEGORY}": 0.05,
    }
    if overrides:
        ps.update(overrides)
    return ps


# ── Gate 1: blocked category ──────────────────────────────────────────────────

def test_blocked_category_unknown():
    result = check_entry("005930", "미분류", 0.80, base_stock())
    assert result.should_buy is False
    assert "blocked_category" in result.reason


def test_blocked_category_custom():
    result = check_entry("005930", "spam_theme", 0.90, base_stock(),
                         blocked_categories={"spam_theme"})
    assert result.should_buy is False


# ── Gate 2: confidence ────────────────────────────────────────────────────────

def test_low_confidence_rejected():
    result = check_entry("005930", CATEGORY, 0.70, base_stock())
    assert result.should_buy is False
    assert any("low_confidence" in f for f in result.failed_filters)


def test_exact_threshold_passes():
    result = check_entry("005930", CATEGORY, 0.75, base_stock(),
                         require_momentum=False, require_regime=False)
    assert result.should_buy is True


# ── Gate 3: liquidity ─────────────────────────────────────────────────────────

def test_illiquid_rejected():
    # ADV60 = 100m KRW -- well below 5m * 100 = 500m
    result = check_entry("000001", CATEGORY, 0.80,
                         base_stock({"avg_daily_value_60d": 100_000_000}),
                         require_momentum=False, require_regime=False)
    assert result.should_buy is False
    assert any("illiquid" in f for f in result.failed_filters)


def test_zero_adv_skipped():
    """ADV60=0 (no data) -- filter is skipped (benefit of doubt)."""
    result = check_entry("000001", CATEGORY, 0.80,
                         base_stock({"avg_daily_value_60d": 0}),
                         require_momentum=False, require_regime=False)
    assert "illiquid" not in " ".join(result.failed_filters)


# ── Gate 4: momentum ──────────────────────────────────────────────────────────

def test_weak_momentum_rejected():
    stock = base_stock({"ma20": 7_000, "ma60": 8_000, "ma200": 9_000})  # inverted
    result = check_entry("005930", CATEGORY, 0.80, stock, require_regime=False)
    assert any("weak_momentum" in f for f in result.failed_filters)


def test_momentum_skipped_when_disabled():
    stock = base_stock({"ma20": 7_000, "ma60": 8_000, "ma200": 9_000})
    result = check_entry("005930", CATEGORY, 0.80, stock,
                         require_momentum=False, require_regime=False)
    assert all("momentum" not in f for f in result.failed_filters)


def test_missing_ma_data_skips_momentum():
    """MA data missing -> momentum filter skip (pass)."""
    stock = base_stock({"ma20": 0, "ma60": 0, "ma200": 0})
    result = check_entry("005930", CATEGORY, 0.80, stock, require_regime=False)
    assert all("momentum" not in f for f in result.failed_filters)


# ── Gate 5: regime ────────────────────────────────────────────────────────────

def test_bear_regime_rejected():
    stock = base_stock({"kospi_close": 2_000, "kospi_ma200": 2_500})
    result = check_entry("005930", CATEGORY, 0.80, stock, require_momentum=False)
    assert any("bear_regime" in f for f in result.failed_filters)


def test_regime_only_for_kr():
    """US stocks are exempt from KOSPI regime filter."""
    stock = base_stock({"market": "NASDAQ", "kospi_close": 1_500, "kospi_ma200": 3_000})
    result = check_entry("AAPL", "빅테크_파트너", 0.80, stock,
                         require_momentum=False)
    assert all("regime" not in f for f in result.failed_filters)


# ── Gate 6: recent crash ──────────────────────────────────────────────────────

def test_recent_crash_rejected():
    stock = base_stock({"min_60d_return": -0.18})  # -18%, below -15%
    result = check_entry("005930", CATEGORY, 0.80, stock,
                         require_momentum=False, require_regime=False)
    assert any("recent_crash" in f for f in result.failed_filters)


def test_acceptable_drawdown_passes():
    stock = base_stock({"min_60d_return": -0.14})  # -14%, above -15%
    result = check_entry("005930", CATEGORY, 0.80, stock,
                         require_momentum=False, require_regime=False)
    assert all("crash" not in f for f in result.failed_filters)


# ── Gate 7: portfolio concentration ──────────────────────────────────────────

def test_portfolio_full_rejected():
    ps = base_portfolio({"n_positions": 15, "max_positions": 15})
    result = check_entry("005930", CATEGORY, 0.80, base_stock(),
                         portfolio_state=ps, require_momentum=False, require_regime=False)
    assert any("portfolio_full" in f for f in result.failed_filters)


def test_category_full_rejected():
    ps = base_portfolio({f"category_weight_{CATEGORY}": 0.25})
    result = check_entry("005930", CATEGORY, 0.80, base_stock(),
                         portfolio_state=ps, require_momentum=False, require_regime=False)
    assert any("category_full" in f for f in result.failed_filters)


# ── Happy path ────────────────────────────────────────────────────────────────

def test_all_gates_pass():
    result = check_entry(
        "005930", CATEGORY, 0.85,
        base_stock(),
        portfolio_state=base_portfolio(),
    )
    assert result.should_buy is True
    assert result.reason == "buy"
    assert result.failed_filters == []


def test_multiple_failures_all_reported():
    """Multiple filter failures should all appear in failed_filters."""
    stock = base_stock({
        "ma20": 7_000, "ma60": 8_000, "ma200": 9_000,   # weak momentum
        "min_60d_return": -0.20,                          # recent crash
        "avg_daily_value_60d": 100_000_000,               # illiquid
    })
    result = check_entry("000001", CATEGORY, 0.50, stock)
    # confidence + illiquid + momentum + crash should all be in failed
    assert len(result.failed_filters) >= 3
    assert result.should_buy is False
