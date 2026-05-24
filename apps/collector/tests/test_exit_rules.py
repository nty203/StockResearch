"""Tests for trading.exit_rules -- 3-tier exit logic."""
import pytest
from src.hundredx.trading.exit_rules import check_exit, update_trailing_high, Position, ExitAction


def make_pos(
    ticker="005930",
    category="수주잔고_선행",
    entry_price=10_000,
    entry_date="2024-01-15",
    shares=100,
    max_close=10_000,
    confidence=0.80,
):
    return Position(
        ticker=ticker,
        category=category,
        entry_price=entry_price,
        entry_date=entry_date,
        shares=shares,
        max_close_since_entry=max_close,
        current_confidence=confidence,
    )


# ── Tier 2: Hard stop ─────────────────────────────────────────────────────────

def test_hard_stop_exactly_20pct():
    pos = make_pos(entry_price=10_000)
    action = check_exit(pos, current_price=8_000, current_date="2024-03-01")
    assert action.action == "sell_all"
    assert action.exit_tier == 2
    assert "hard_stop" in action.reason


def test_hard_stop_below_20pct():
    pos = make_pos(entry_price=10_000)
    action = check_exit(pos, current_price=7_500, current_date="2024-03-01")
    assert action.action == "sell_all"
    assert action.exit_tier == 2


def test_no_hard_stop_at_minus_19pct():
    pos = make_pos(entry_price=10_000)
    action = check_exit(pos, current_price=8_100, current_date="2024-03-01")
    # Not a hard stop (but may be another tier or hold)
    assert not (action.exit_tier == 2 and "hard_stop" in action.reason)


def test_confidence_decay_trigger():
    pos = make_pos(entry_price=10_000, confidence=0.45)  # below 0.50
    action = check_exit(pos, current_price=11_000, current_date="2024-06-01")
    assert action.action == "sell_all"
    assert action.exit_tier == 2
    assert "signal_decay" in action.reason


def test_confidence_above_threshold_holds():
    pos = make_pos(entry_price=10_000, confidence=0.75)
    action = check_exit(pos, current_price=11_000, current_date="2024-06-01")
    assert "signal_decay" not in action.reason


def test_refutation_flag_sells_all():
    pos = make_pos(entry_price=10_000)
    action = check_exit(pos, current_price=12_000, current_date="2024-06-01",
                        refutation_flag=True)
    assert action.action == "sell_all"
    assert action.exit_tier == 2
    assert "refutation" in action.reason


def test_hard_stop_priority_over_trailing():
    """Hard stop should fire even when trailing stop would also fire."""
    pos = make_pos(entry_price=10_000, max_close=15_000)
    action = check_exit(pos, current_price=7_000, current_date="2024-03-01",
                        atr_20d=500)  # atr trailing would also fire
    assert action.exit_tier == 2  # hard stop wins


# ── Tier 1: Trailing ATR stop ─────────────────────────────────────────────────

def test_trailing_atr_fires():
    # max_close = 15000, current = 12000
    # atr = 500, pct = 500/12000 ~= 0.0417
    # trailing_stop = 15000 * (1 - 3 * 0.0417) = 15000 * 0.875 = 13125
    # 12000 <= 13125 -> should fire
    pos = make_pos(entry_price=10_000, max_close=15_000)
    action = check_exit(pos, current_price=12_000, current_date="2024-06-01",
                        atr_20d=500)
    assert action.action == "sell_all"
    assert action.exit_tier == 1
    assert "trailing_stop" in action.reason


def test_trailing_atr_hold_when_above():
    # max_close = 12000, current = 11500
    # atr = 200, pct = 200/11500 ~= 0.0174
    # trailing_stop = 12000 * (1 - 3 * 0.0174) = 12000 * 0.948 = 11376
    # 11500 > 11376 -> hold
    pos = make_pos(entry_price=10_000, max_close=12_000)
    action = check_exit(pos, current_price=11_500, current_date="2024-06-01",
                        atr_20d=200)
    assert action.action == "hold"


def test_trailing_atr_skipped_when_none():
    pos = make_pos(entry_price=10_000, max_close=15_000)
    action = check_exit(pos, current_price=12_000, current_date="2024-06-01",
                        atr_20d=None)
    # Without ATR, trailing stop is disabled
    assert action.exit_tier != 1


def test_trailing_stop_detail_recorded():
    pos = make_pos(entry_price=10_000, max_close=15_000)
    action = check_exit(pos, current_price=12_000, current_date="2024-06-01",
                        atr_20d=500)
    assert "trailing_stop" in action.details
    assert "atr_pct" in action.details


# ── Tier 3: Time stop ─────────────────────────────────────────────────────────

def test_time_stop_24m_full_exit():
    # held 25 months, multiplier 1.5x < 2x
    pos = make_pos(entry_price=10_000, entry_date="2022-01-01")
    action = check_exit(pos, current_price=15_000, current_date="2024-02-01")
    assert action.action == "sell_all"
    assert action.exit_tier == 3
    assert "time_stop_24m" in action.reason


def test_time_stop_12m_partial_exit():
    # held 13 months, multiplier 1.5x < 2x
    pos = make_pos(entry_price=10_000, entry_date="2023-01-01")
    action = check_exit(pos, current_price=15_000, current_date="2024-02-01")
    assert action.action == "sell_partial"
    assert action.sell_fraction == 0.5
    assert action.exit_tier == 3


def test_time_stop_12m_achieved_target_holds():
    # held 13 months, multiplier 3.0x > 2x -> no time stop
    pos = make_pos(entry_price=10_000, entry_date="2023-01-01")
    action = check_exit(pos, current_price=30_000, current_date="2024-02-01")
    assert "time_stop" not in action.reason


def test_no_stop_short_hold():
    # held 6 months -- time stops don't apply
    pos = make_pos(entry_price=10_000, entry_date="2024-01-01")
    action = check_exit(pos, current_price=11_000, current_date="2024-07-01")
    assert action.exit_tier == 0
    assert action.action == "hold"


# ── update_trailing_high ──────────────────────────────────────────────────────

def test_trailing_high_updated():
    pos = make_pos(max_close=10_000)
    updated = update_trailing_high(pos, 12_000)
    assert updated.max_close_since_entry == 12_000


def test_trailing_high_not_lowered():
    pos = make_pos(max_close=15_000)
    updated = update_trailing_high(pos, 12_000)
    assert updated.max_close_since_entry == 15_000


# ── ExitAction fields ─────────────────────────────────────────────────────────

def test_hold_action_fields():
    pos = make_pos(entry_price=10_000)
    action = check_exit(pos, current_price=11_000, current_date="2024-06-01")
    assert action.action == "hold"
    assert action.sell_fraction == 0.0
    assert action.exit_tier == 0


def test_sell_all_fraction_is_1():
    pos = make_pos(entry_price=10_000)
    action = check_exit(pos, current_price=7_500, current_date="2024-06-01")
    assert action.sell_fraction == 1.0


def test_details_always_present():
    pos = make_pos(entry_price=10_000)
    action = check_exit(pos, current_price=11_000, current_date="2024-06-01")
    assert "days_held" in action.details
    assert "months_held" in action.details
    assert "current_multiplier" in action.details
