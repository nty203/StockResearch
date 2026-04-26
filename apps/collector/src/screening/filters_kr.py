"""Korean stock screening filters (f01–f22) from report 3-B.

Mandatory filters (ALL must pass):
  f01: market cap >= threshold (default 300B KRW)
  f02: avg daily trading value >= threshold (default 5B KRW)
  f03: revenue growth YoY >= threshold (default 20%)
  f08: order backlog exists or revenue > 0 (proxy)
  f09: debt ratio <= threshold (default 200%)

Scoring filters (f04–f07, f10–f22): contribute to score.
"""
from __future__ import annotations
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

DEFAULT_SETTINGS = {
    "kr_min_market_cap": 300_000_000_000,  # 300B KRW
    "kr_min_daily_value": 5_000_000_000,   # 5B KRW
    "kr_min_revenue_growth": 20.0,          # %
    "kr_max_debt_ratio": 200.0,             # %
}


@dataclass
class FilterResult:
    ticker: str
    passed: bool
    score: float = 0.0
    failed_filters: list[str] = field(default_factory=list)
    scores_by_filter: dict[str, float] = field(default_factory=dict)


def _pct_change(new, old) -> float | None:
    if old is None or old == 0 or new is None:
        return None
    return (new - old) / abs(old) * 100


def apply_kr_filters(stock_data: dict, settings: dict | None = None) -> FilterResult:
    """Apply KR filters to a single stock's data.

    stock_data keys:
      ticker, market_cap, avg_daily_value, revenue_ttm, revenue_prev,
      op_income_ttm, op_margin_ttm, debt_ratio, roe, roic, fcf,
      revenue_2y_ago, order_backlog, foreign_ownership_pct,
      price, price_52w_high, rs_score, insider_buy_pct
    """
    cfg = {**DEFAULT_SETTINGS, **(settings or {})}
    ticker = stock_data.get("ticker", "")
    result = FilterResult(ticker=ticker, passed=False)
    score = 0.0
    failed: list[str] = []

    # ── Mandatory filters ──────────────────────────────────────────────────
    # f01: only exclude when market_cap is known AND below threshold.
    # When None (no data), pass — universe is already limited to is_active=True.
    mc = stock_data.get("market_cap")
    if mc is not None and mc < cfg["kr_min_market_cap"]:
        failed.append("f01_market_cap")

    dv = stock_data.get("avg_daily_value")
    if dv is not None and dv < cfg["kr_min_daily_value"]:
        failed.append("f02_daily_value")

    rev_ttm = stock_data.get("revenue_ttm")
    rev_prev = stock_data.get("revenue_prev")
    rev_growth = _pct_change(rev_ttm, rev_prev)
    # Only exclude when we have prior-year data and growth is below threshold.
    # When rev_growth is None (no prior data yet), pass — scoring will be low.
    if rev_growth is not None and rev_growth < cfg["kr_min_revenue_growth"]:
        failed.append("f03_revenue_growth")

    debt_ratio = stock_data.get("debt_ratio")
    if debt_ratio is not None and debt_ratio > cfg["kr_max_debt_ratio"]:
        failed.append("f09_debt_ratio")

    # f08: order backlog proxy — has revenue or backlog data
    backlog = stock_data.get("order_backlog")
    if backlog is None and (rev_ttm is None or rev_ttm <= 0):
        failed.append("f08_backlog")

    if failed:
        result.passed = False
        result.failed_filters = failed
        return result

    result.passed = True

    # ── Scoring filters ────────────────────────────────────────────────────
    # f04: Revenue growth acceleration
    rev_2y = stock_data.get("revenue_2y_ago")
    growth_2y = _pct_change(rev_prev, rev_2y)
    if rev_growth is not None and growth_2y is not None and rev_growth > growth_2y:
        s = min(10, (rev_growth - growth_2y) / 5)
        score += s
        result.scores_by_filter["f04"] = s

    # f05: Operating margin improvement
    op_margin = stock_data.get("op_margin_ttm")
    op_margin_prev = stock_data.get("op_margin_prev")
    if op_margin is not None and op_margin > 10:
        s = min(8, op_margin / 5)
        score += s
        result.scores_by_filter["f05_op_margin"] = s
    if op_margin is not None and op_margin_prev is not None and op_margin > op_margin_prev:
        s = min(5, (op_margin - op_margin_prev))
        score += s
        result.scores_by_filter["f05_margin_trend"] = s

    # f06: ROIC > 15%
    roic = stock_data.get("roic")
    if roic is not None and roic > 15:
        s = min(8, (roic - 15) / 2)
        score += s
        result.scores_by_filter["f06_roic"] = s

    # f07: FCF positive
    fcf = stock_data.get("fcf")
    if fcf is not None and fcf > 0:
        score += 5
        result.scores_by_filter["f07_fcf"] = 5.0

    # f10: Foreign ownership >= 10%
    fown = stock_data.get("foreign_ownership_pct")
    if fown is not None and fown >= 10:
        score += 4
        result.scores_by_filter["f10_foreign"] = 4.0

    # f11: RS score (relative strength) >= 70
    rs = stock_data.get("rs_score")
    if rs is not None and rs >= 70:
        s = min(6, (rs - 70) / 5)
        score += s
        result.scores_by_filter["f11_rs"] = s

    # f12: Price within 20% of 52w high (momentum)
    price = stock_data.get("price")
    high_52w = stock_data.get("price_52w_high")
    if price and high_52w and high_52w > 0:
        pct_from_high = (high_52w - price) / high_52w * 100
        if pct_from_high <= 20:
            s = (20 - pct_from_high) / 4
            score += s
            result.scores_by_filter["f12_momentum"] = s

    result.score = round(score, 2)
    return result
