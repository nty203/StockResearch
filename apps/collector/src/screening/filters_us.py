"""US stock screening filters (us01–us20) from report 3-C.

Mandatory filters (ALL must pass):
  us01: market cap >= threshold (default $500M)
  us02: avg daily dollar volume >= threshold (default $5M)
  us03: revenue growth YoY >= threshold (default 15%)
  us08: gross margin >= threshold (default 40%)
  us09: debt/equity <= threshold (default 300%)

Scoring filters contribute to score.
"""
from __future__ import annotations
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

DEFAULT_SETTINGS = {
    "us_min_market_cap": 500_000_000,   # $500M
    "us_min_daily_value": 5_000_000,    # $5M
    "us_min_revenue_growth": 15.0,       # %
    "us_min_gross_margin": 40.0,         # %
    "us_max_debt_equity": 300.0,         # %
}


@dataclass
class USFilterResult:
    ticker: str
    passed: bool
    score: float = 0.0
    failed_filters: list[str] = field(default_factory=list)
    scores_by_filter: dict[str, float] = field(default_factory=dict)


def _pct_change(new, old) -> float | None:
    if old is None or old == 0 or new is None:
        return None
    return (new - old) / abs(old) * 100


def apply_us_filters(stock_data: dict, settings: dict | None = None) -> USFilterResult:
    """Apply US filters to a single stock's data.

    stock_data keys: ticker, market_cap, avg_daily_value, revenue_ttm, revenue_prev,
      gross_margin, op_margin, debt_equity, roe, roic, fcf, revenue_2y_ago,
      price, price_52w_high, rs_score, institutional_ownership_pct, ps_ratio, pe_ratio
    """
    cfg = {**DEFAULT_SETTINGS, **(settings or {})}
    ticker = stock_data.get("ticker", "")
    result = USFilterResult(ticker=ticker, passed=False)
    score = 0.0
    failed: list[str] = []

    # ── Mandatory filters ──────────────────────────────────────────────────
    mc = stock_data.get("market_cap")
    if mc is None or mc < cfg["us_min_market_cap"]:
        failed.append("us01_market_cap")

    dv = stock_data.get("avg_daily_value")
    if dv is None or dv < cfg["us_min_daily_value"]:
        failed.append("us02_daily_value")

    rev_ttm = stock_data.get("revenue_ttm")
    rev_prev = stock_data.get("revenue_prev")
    rev_growth = _pct_change(rev_ttm, rev_prev)
    if rev_growth is None or rev_growth < cfg["us_min_revenue_growth"]:
        failed.append("us03_revenue_growth")

    gm = stock_data.get("gross_margin")
    if gm is None or gm < cfg["us_min_gross_margin"]:
        failed.append("us08_gross_margin")

    de = stock_data.get("debt_equity")
    if de is not None and de > cfg["us_max_debt_equity"]:
        failed.append("us09_debt_equity")

    if failed:
        result.passed = False
        result.failed_filters = failed
        return result

    result.passed = True

    # ── Scoring filters ────────────────────────────────────────────────────
    # us04: Revenue acceleration
    rev_2y = stock_data.get("revenue_2y_ago")
    growth_2y = _pct_change(rev_prev, rev_2y)
    if rev_growth is not None and growth_2y is not None and rev_growth > growth_2y:
        s = min(10, (rev_growth - growth_2y) / 5)
        score += s
        result.scores_by_filter["us04_accel"] = s

    # us05: Operating margin expansion
    op_margin = stock_data.get("op_margin")
    op_margin_prev = stock_data.get("op_margin_prev")
    if op_margin is not None and op_margin > 15:
        s = min(8, op_margin / 5)
        score += s
        result.scores_by_filter["us05_op_margin"] = s
    if op_margin is not None and op_margin_prev is not None and op_margin > op_margin_prev:
        s = min(5, op_margin - op_margin_prev)
        score += s
        result.scores_by_filter["us05_margin_trend"] = s

    # us06: ROIC > 20%
    roic = stock_data.get("roic")
    if roic is not None and roic > 20:
        s = min(8, (roic - 20) / 2)
        score += s
        result.scores_by_filter["us06_roic"] = s

    # us07: FCF yield > 3%
    fcf = stock_data.get("fcf")
    mc2 = stock_data.get("market_cap")
    if fcf is not None and mc2 is not None and mc2 > 0:
        fcf_yield = fcf / mc2 * 100
        if fcf_yield > 3:
            score += 5
            result.scores_by_filter["us07_fcf_yield"] = 5.0

    # us10: Institutional ownership >= 30%
    inst = stock_data.get("institutional_ownership_pct")
    if inst is not None and inst >= 30:
        score += 4
        result.scores_by_filter["us10_institutional"] = 4.0

    # us11: RS score >= 70
    rs = stock_data.get("rs_score")
    if rs is not None and rs >= 70:
        s = min(6, (rs - 70) / 5)
        score += s
        result.scores_by_filter["us11_rs"] = s

    # us12: Price within 20% of 52w high
    price = stock_data.get("price")
    high_52w = stock_data.get("price_52w_high")
    if price and high_52w and high_52w > 0:
        pct_from_high = (high_52w - price) / high_52w * 100
        if pct_from_high <= 20:
            s = (20 - pct_from_high) / 4
            score += s
            result.scores_by_filter["us12_momentum"] = s

    # us15: P/S ratio < 20 (value filter)
    ps = stock_data.get("ps_ratio")
    if ps is not None and ps < 20:
        s = max(0, (20 - ps) / 4)
        score += s
        result.scores_by_filter["us15_ps"] = s

    result.score = round(score, 2)
    return result
