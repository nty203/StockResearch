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
from ..upsert import get_client, upsert_batch, pipeline_run
from ..utils.db_fetch import bulk_fetch_financials

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


def _bulk_fetch_stock_data(supabase_client, tickers: list[str]) -> dict[str, dict]:
    """Batch fetch all data for a list of tickers — delegates to shared utility."""
    return bulk_fetch_financials(supabase_client, tickers)


def _categorize_score(raw_score: float, filter_result) -> dict[str, float]:
    """Map raw filter scores to the 8 category weights."""
    scores = filter_result.scores_by_filter if filter_result else {}

    # Simple mapping: sum of related filter scores → category raw score
    growth = (scores.get("f03", 0) + scores.get("f04", 0)
              + scores.get("f13_bcr", 0) + scores.get("f14_backlog_growth", 0)
              + scores.get("us03", 0) + scores.get("us04_accel", 0))
    momentum = (scores.get("f11_rs", 0) + scores.get("f12_momentum", 0)
                + scores.get("us11_rs", 0) + scores.get("us12_momentum", 0))
    quality = (scores.get("f05_op_margin", 0) + scores.get("f05_margin_trend", 0)
               + scores.get("f15_opm_inflection", 0)
               + scores.get("f06_roic", 0) + scores.get("f07_fcf", 0)
               + scores.get("us05_op_margin", 0) + scores.get("us06_roic", 0))
    sponsorship = scores.get("f10_foreign", 0) + scores.get("us10_institutional", 0)
    value = scores.get("us15_ps", 0)
    safety = scores.get("safety_score", 5.0)   # from filters: debt_ratio based
    size = scores.get("size_score", 5.0)        # from filters: avg_daily_value based

    return {
        "growth": min(100, growth),
        "momentum": min(100, momentum),
        "quality": min(100, quality),
        "sponsorship": min(100, sponsorship),
        "value": min(100, value),
        "safety": min(100, safety),
        "size": min(100, size),
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

    tickers = [s["ticker"] for s in stocks]
    market_by_ticker = {s["ticker"]: s.get("market", "") for s in stocks}

    # Batch fetch all data — 2 queries per 50-ticker batch vs 3×N individual queries
    BATCH = 50
    bulk_data: dict[str, dict] = {}
    for i in range(0, len(tickers), BATCH):
        batch = tickers[i : i + BATCH]
        bulk_data.update(_bulk_fetch_stock_data(client, batch))

    raw_scores: list[dict] = []
    for stock in stocks:
        ticker = stock["ticker"]
        market = market_by_ticker.get(ticker, "")
        try:
            stock_data = bulk_data.get(ticker, {"ticker": ticker})
            stock_data["ticker"] = ticker
            stock_data["market"] = market

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
                    "score_10x": 0.0,
                    "percentile": 0.0,
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
                "scores_by_filter": filter_result.scores_by_filter,
                "market_gate": market_gate,
                "score_10x": raw_score,
                "percentile": 0.0,  # filled in pass 2
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
    with pipeline_run(client, "scores") as (rows_out, _):
        count = upsert_batch(client, "screen_scores", rows, on_conflict="ticker,run_date")
        rows_out[0] = count
    logger.info("Scores upserted %d rows for %s", count, run_date or "today")
    return count


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None, help="Run date YYYY-MM-DD")
    args = parser.parse_args()
    run(args.date)
