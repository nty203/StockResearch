"""Tests for trading.position_sizer -- Half-Kelly + Vol Targeting."""
import math
import pytest
from src.hundredx.trading.position_sizer import (
    compute_position_size,
    SizingResult,
    MAX_SINGLE_WEIGHT,
    MAX_CATEGORY_WEIGHT,
    MIN_CONFIDENCE_SCALE_LOW,
    MIN_CONFIDENCE_SCALE_HIGH,
    TARGET_CONTRIBUTION_VOL,
    CATEGORY_DEFAULT_PAYOFF,
)

CAT_BACKLOG = "수주잔고_선행"
CAT_PROFIT  = "수익성_급전환"
CAT_CLINICAL = "임상_파이프라인"
CAT_POLICY  = "정책_수혜"


def test_returns_sizing_result():
    result = compute_position_size(CAT_BACKLOG, 0.85, ann_vol=0.40)
    assert isinstance(result, SizingResult)
    assert 0.0 <= result.weight <= MAX_SINGLE_WEIGHT


def test_portfolio_full_returns_zero():
    result = compute_position_size(
        CAT_BACKLOG, 0.90, ann_vol=0.40,
        n_current_positions=15, max_positions=15,
    )
    assert result.weight == 0.0
    assert result.shares == 0
    assert result.reason == "portfolio_full"


# ── Kelly fraction ────────────────────────────────────────────────────────────

def test_kelly_positive_for_edge():
    """Kelly > 0 when E[R] > 0: p*(b+1) > 1 -> p > 1/(b+1)."""
    # b=6.0 (수주잔고_선행 default), so threshold = 1/7 ~= 0.143
    result = compute_position_size(CAT_BACKLOG, 0.85, ann_vol=0.40)
    assert result.kelly_fraction > 0.0


def test_kelly_zero_for_no_edge():
    """Kelly <= 0 when confidence below breakeven threshold -> weight = 0."""
    # b=6, p=0.10 -> kelly = (0.10*7 - 1)/6 = (0.7-1)/6 < 0 -> 0
    result = compute_position_size(CAT_BACKLOG, 0.10, ann_vol=0.40)
    assert result.weight == 0.0


def test_kelly_is_half():
    """half_kelly = kelly * 0.5."""
    r = compute_position_size(CAT_BACKLOG, 0.85, ann_vol=0.40)
    b = CATEGORY_DEFAULT_PAYOFF[CAT_BACKLOG]
    p = 0.85
    kelly_raw = (p * (b + 1) - 1) / b
    expected_half = kelly_raw * 0.5
    assert abs(r.kelly_fraction - expected_half) < 1e-6


# ── Volatility targeting ──────────────────────────────────────────────────────

def test_high_vol_smaller_vol_fraction():
    r_low = compute_position_size(CAT_PROFIT, 0.85, ann_vol=0.20)
    r_high = compute_position_size(CAT_PROFIT, 0.85, ann_vol=0.80)
    assert r_low.vol_fraction >= r_high.vol_fraction


def test_vol_targeting_formula():
    """vol_fraction stores the raw (uncapped) vol_weight = TARGET_VOL / (ann_vol * sqrt(corr=0.3))."""
    ann_vol = 0.45
    corr = 0.3
    expected_raw = TARGET_CONTRIBUTION_VOL / (ann_vol * math.sqrt(corr))
    result = compute_position_size(CAT_BACKLOG, 0.95, ann_vol=ann_vol)
    # vol_fraction is the raw value; the cap is applied only to the final weight
    assert abs(result.vol_fraction - expected_raw) < 1e-4
    # The final weight is capped at MAX_SINGLE_WEIGHT if expected_raw exceeds it
    assert result.weight <= MAX_SINGLE_WEIGHT + 1e-9


# ── Confidence scaling ────────────────────────────────────────────────────────

def test_conf_at_low_threshold_scale_zero():
    """conf=0.75 -> conf_scale=0 -> weight=0."""
    result = compute_position_size(CAT_BACKLOG, 0.75, ann_vol=0.40)
    assert result.weight == 0.0
    assert result.confidence_scale == 0.0


def test_conf_at_high_threshold_scale_one():
    """conf=0.95 -> conf_scale=1.0."""
    result = compute_position_size(CAT_BACKLOG, 0.95, ann_vol=0.40)
    assert result.confidence_scale == 1.0


def test_conf_midpoint_scale_half():
    """conf=0.85 -> conf_scale=0.5."""
    result = compute_position_size(CAT_BACKLOG, 0.85, ann_vol=0.40)
    expected_scale = (0.85 - MIN_CONFIDENCE_SCALE_LOW) / (MIN_CONFIDENCE_SCALE_HIGH - MIN_CONFIDENCE_SCALE_LOW)
    assert abs(result.confidence_scale - expected_scale) < 1e-6


# ── Caps and constraints ──────────────────────────────────────────────────────

def test_single_weight_capped_at_10pct():
    result = compute_position_size(CAT_BACKLOG, 0.99, ann_vol=0.05)
    assert result.weight <= MAX_SINGLE_WEIGHT + 1e-9


def test_category_constraint():
    # category already at 20% -> remaining = 5%
    result = compute_position_size(
        CAT_BACKLOG, 0.95, ann_vol=0.05,
        category_used_weight=0.20,
    )
    assert result.weight <= (MAX_CATEGORY_WEIGHT - 0.20) + 1e-9


def test_category_full_returns_zero():
    result = compute_position_size(
        CAT_BACKLOG, 0.95, ann_vol=0.05,
        category_used_weight=0.25,
    )
    assert result.weight == 0.0


# ── Shares calculation ────────────────────────────────────────────────────────

def test_shares_calculated_correctly():
    result = compute_position_size(
        CAT_BACKLOG, 0.90, ann_vol=0.40,
        portfolio_value=100_000_000,
        current_price=10_000,
    )
    if result.weight > 0:
        expected_shares = int(100_000_000 * result.weight // 10_000)
        assert result.shares == expected_shares


def test_shares_zero_without_portfolio_value():
    result = compute_position_size(CAT_BACKLOG, 0.90, ann_vol=0.40)
    assert result.shares == 0


# ── Category payoff ratios ────────────────────────────────────────────────────

def test_custom_payoff_ratio_used():
    r_custom = compute_position_size(CAT_BACKLOG, 0.85, ann_vol=0.40, payoff_ratio=2.0)
    assert r_custom.details["payoff_b"] == 2.0


def test_clinical_pipeline_higher_payoff():
    """임상_파이프라인 has highest default payoff (7.0) -> higher kelly."""
    r_clinical = compute_position_size(CAT_CLINICAL, 0.85, ann_vol=0.40)
    r_policy = compute_position_size(CAT_POLICY, 0.85, ann_vol=0.40)
    assert r_clinical.kelly_fraction >= r_policy.kelly_fraction


# ── SizingResult fields ───────────────────────────────────────────────────────

def test_result_has_all_details():
    r = compute_position_size(CAT_BACKLOG, 0.85, ann_vol=0.40)
    for key in ("kelly_raw", "half_kelly", "vol_weight", "payoff_b",
                "conf", "ann_vol", "category_used", "category_remaining"):
        assert key in r.details


def test_reason_sized_when_positive():
    r = compute_position_size(CAT_BACKLOG, 0.90, ann_vol=0.40)
    if r.weight > 0:
        assert r.reason == "sized"
