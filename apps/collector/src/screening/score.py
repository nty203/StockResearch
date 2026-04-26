"""10X score calculator — 2-pass: raw → percentile, 8 category weighted sum.

Weights (sum = 100):
  Growth: 28, Momentum: 22, Quality: 18, Sponsorship: 12,
  Value: 8, Safety: 7, Size: 5
"""
from __future__ import annotations
import logging
from datetime import date

import pandas as pd

from .filters_kr import apply_kr_filters, FilterResult
from .filters_us import apply_us_filters
from .peak_risk import apply_peak_risk_penalty
from .settings_loader import load_settings
from ..upsert import get_client, upsert_batch

logger = logging.getLogger(__name__)

DEFAULT_WEIGHTS = {
    "growth": 28,
    "momentum": 22,
    "quality": 18,
    "sponsorship": 12,
    "value": 8,
    "safety": 7,
    "size": 5,
}

MARKET_GATE_MA = 200  # MA200 threshold


def _compute_market_gate(supabase_client) -> float:
    """Returns 1.0 if KOSPI and S&P500 are above MA200, else 0.7."""
    try:
        for index_ticker in ("KOSPI", "SPY"):
            res = (
                supabase_client.table("prices_daily")
                .select("close")
                .eq("ticker", index_ticker)
                .order("date", desc=True)
                .limit(MARKET_GATE_MA + 1)
                .execute()
            )
            prices = [r["close"] for r in (res.data or [])]
            if len(prices) < MARKET_GATE_MA:
                continue
            current = prices[0]
            ma200 = sum(prices[:MARKET_GATE_MA]) / MARKET_GATE_MA
            if current < ma200:
                return 0.7
        return 1.0
    except Exception as e:
        logger.warning("Market gate check failed: %s", e)
        return 1.0


def _build_stock_data(supabase_client, ticker: str) -> dict:
    """Fetch and assemble stock data needed for scoring."""
    data: dict = {"ticker": ticker}

    # Latest financials (last 2 quarters)
    fin_res = (
        supabase_client.table("financials_q")
        .select("fq, revenue, op_income, op_margin, roe, roic, fcf, debt_ratio")
        .eq("ticker", ticker)
        .order("fq", desc=True)
        .limit(8)
        .execute()
    )
    fins = fin_res.data or []
    if fins:
        latest = fins[0]
        prev = fins[1] if len(fins) > 1 else {}
        older = fins[3] if len(fins) > 3 else {}
        # Annualise TTM revenue (sum of 4 quarters)
        data["revenue_ttm"] = sum(f.get("revenue", 0) or 0 for f in fins[:4]) or None
        data["revenue_prev"] = sum(f.get("revenue", 0) or 0 for f in fins[4:8]) or None
        data["revenue_2y_ago"] = None  # would need 8+ quarters
        data["op_margin_ttm"] = latest.get("op_margin")
        data["op_margin_prev"] = prev.get("op_margin")
        data["roic"] = latest.get("roic")
        data["fcf"] = latest.get("fcf")
        data["debt_ratio"] = latest.get("debt_ratio")

    # Price data
    price_res = (
        supabase_client.table("prices_daily")
        .select("close, volume")
        .eq("ticker", ticker)
        .order("date", desc=True)
        .limit(252)
        .execute()
    )
    prices = price_res.data or []
    if prices:
        data["price"] = prices[0]["close"]
        data["price_52w_high"] = max(p["close"] for p in prices)
        # Use 20-day average volume × price for trading value (avoids single-day zero)
        recent = prices[:20]
        avg_vol = sum(p.get("volume") or 0 for p in recent) / len(recent)
        avg_price = sum(p["close"] for p in recent) / len(recent)
        data["avg_daily_value"] = avg_vol * avg_price if avg_vol > 0 else None

    # Stock meta
    stock_res = (
        supabase_client.table("stocks")
        .select("market")
        .eq("ticker", ticker)
        .single()
        .execute()
    )
    if stock_res.data:
        data["market"] = stock_res.data.get("market")

    return data


def _categorize_score(raw_score: float, filter_result) -> dict[str, float]:
    """Map raw filter scores to the 8 category weights."""
    scores = filter_result.scores_by_filter if filter_result else {}

    # Simple mapping: sum of related filter scores → category raw score
    growth = scores.get("f03", 0) + scores.get("f04", 0) + scores.get("us03", 0) + scores.get("us04_accel", 0)
    momentum = scores.get("f11_rs", 0) + scores.get("f12_momentum", 0) + scores.get("us11_rs", 0) + scores.get("us12_momentum", 0)
    quality = scores.get("f05_op_margin", 0) + scores.get("f06_roic", 0) + scores.get("f07_fcf", 0) + scores.get("us05_op_margin", 0) + scores.get("us06_roic", 0)
    sponsorship = scores.get("f10_foreign", 0) + scores.get("us10_institutional", 0)
    value = scores.get("us15_ps", 0)
    safety = 10 - (10 if scores.get("debt_penalty") else 0)
    size = scores.get("f01", 0) + scores.get("us01", 0)

    return {
        "growth": min(100, growth),
        "momentum": min(100, momentum),
        "quality": min(100, quality),
        "sponsorship": min(100, sponsorship),
        "value": min(100, value),
        "safety": max(0, min(100, safety + 5)),
        "size": min(100, size + 5),
    }


def compute_scores(run_date: str | None = None) -> list[dict]:
    """Compute screen_scores for all active stocks."""
    client = get_client()
    settings = load_settings(client)
    weights = settings.get("score_weights", DEFAULT_WEIGHTS)
    market_gate_enabled = settings.get("market_gate_enabled", True)

    if run_date is None:
        run_date = date.today().isoformat()

    market_gate = _compute_market_gate(client) if market_gate_enabled else 1.0

    res = client.table("stocks").select("ticker, market").eq("is_active", True).execute()
    stocks = res.data or []

    raw_scores: list[dict] = []
    for stock in stocks:
        ticker = stock["ticker"]
        market = stock.get("market", "")
        try:
            stock_data = _build_stock_data(client, ticker)
            stock_data["ticker"] = ticker

            if market in ("KOSPI", "KOSDAQ"):
                filter_result = apply_kr_filters(stock_data, settings)
            else:
                filter_result = apply_us_filters(stock_data, settings)

            if not filter_result.passed:
                raw_scores.append({
                    "ticker": ticker,
                    "growth": 0, "momentum": 0, "quality": 0, "sponsorship": 0,
                    "value": 0, "safety": 0, "size": 0,
                    "market_gate": market_gate,
                    "score_10x": 0,
                    "percentile": 0,
                    "passed": False,
                    "failed_filters": filter_result.failed_filters,
                    "run_date": run_date,
                })
                continue

            cats = _categorize_score(filter_result.score, filter_result)
            raw_score = sum(cats[c] * weights.get(c, DEFAULT_WEIGHTS[c]) / 100 for c in cats)

            # Apply peak risk penalty
            penalty = apply_peak_risk_penalty(stock_data)
            raw_score = max(0, raw_score - penalty)

            raw_scores.append({
                "ticker": ticker,
                **cats,
                "market_gate": market_gate,
                "score_10x": raw_score,
                "percentile": 0,  # filled in pass 2
                "passed": True,
                "failed_filters": [],
                "run_date": run_date,
            })
        except Exception as e:
            logger.warning("Score error %s: %s", ticker, e)

    if not raw_scores:
        return []

    # Pass 2: percentile within passed universe
    df = pd.DataFrame(raw_scores)
    passed_mask = df["passed"] == True
    if passed_mask.sum() > 0:
        df.loc[passed_mask, "percentile"] = (
            df.loc[passed_mask, "score_10x"].rank(pct=True) * 100
        ).round(1)

    return df.to_dict(orient="records")


def run(run_date: str | None = None) -> int:
    rows = compute_scores(run_date)
    if not rows:
        return 0
    client = get_client()
    count = upsert_batch(client, "screen_scores", rows, on_conflict="ticker,run_date")
    logger.info("Scores upserted %d rows for %s", count, run_date or "today")
    return count


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None, help="Run date YYYY-MM-DD")
    args = parser.parse_args()
    run(args.date)
