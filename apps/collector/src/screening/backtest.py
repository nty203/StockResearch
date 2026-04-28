"""Point-in-time backtest — validates filter/score against 2020-2024 history.

Uses:
  - FinanceDataReader for KR prices (includes delisted)
  - Stooq CSV for US prices (free, includes delisted)

Reports: hit rate of 10x screened stocks that actually achieved 10x.
Saves per-stock results to backtest_results with category attribution.
"""
from __future__ import annotations
import logging
from datetime import date, timedelta

import FinanceDataReader as fdr
import pandas as pd

from .filters_kr import apply_kr_filters
from .filters_us import apply_us_filters
from ..upsert import get_client

logger = logging.getLogger(__name__)

BACKTEST_START = "2020-01-01"
BACKTEST_END = "2024-12-31"


def _get_price_on_date(ticker: str, target_date: str, market: str) -> float | None:
    """Fetch closing price closest to target_date."""
    try:
        df = fdr.DataReader(ticker, target_date, target_date)
        if not df.empty:
            return float(df["Close"].iloc[0])
    except Exception as e:
        logger.debug("Price fetch error %s %s: %s", ticker, target_date, e)
    return None


def _derive_primary_rise_category(cats: dict, scores_by_filter: dict | None) -> str | None:
    """Determine primary rise category from category scores and filter contributions."""
    if not scores_by_filter:
        # Fall back to highest scoring category
        if not cats:
            return None
        top = max(cats.items(), key=lambda x: x[1] if isinstance(x[1], (int, float)) else 0)
        cat_map = {
            "growth": "수주잔고_선행",
            "quality": "수익성_급전환",
            "sponsorship": "빅테크_파트너",
            "momentum": "플랫폼_독점",
        }
        return cat_map.get(top[0])

    # Check each rise category by summing its indicator filter scores
    scores = {
        "수주잔고_선행": (scores_by_filter.get("f13_bcr", 0) * 2
                         + scores_by_filter.get("f14_backlog_growth", 0) * 2
                         + scores_by_filter.get("f03", 0) * 0.5),
        "수익성_급전환": (scores_by_filter.get("f15_opm_inflection", 0) * 3
                         + scores_by_filter.get("f05_margin_trend", 0) * 1.5),
        "플랫폼_독점": (scores_by_filter.get("f06_roic", 0)
                        + scores_by_filter.get("f05_op_margin", 0)
                        + scores_by_filter.get("f07_fcf", 0)),
        "빅테크_파트너": (scores_by_filter.get("f10_foreign", 0) * 3
                         + scores_by_filter.get("us10_institutional", 0) * 3),
    }
    best = max(scores.items(), key=lambda x: x[1])
    return best[0] if best[1] > 0 else None


def run_backtest(target_date: str = BACKTEST_START) -> dict:
    """Run point-in-time backtest for a specific date.

    Saves per-stock results to backtest_results with category attribution.
    Returns: {screened: int, achieved_10x: int, hit_rate: float, run_id: str}
    """
    client = get_client()

    # Fetch screen_scores with category and filter detail
    res = client.table("screen_scores").select(
        "ticker, passed, score_10x, growth, momentum, quality, sponsorship, value, safety, size, scores_by_filter"
    ).eq("run_date", target_date).execute()
    scores = res.data or []

    screened = [s for s in scores if s["passed"] and (s.get("score_10x") or 0) >= 65]
    logger.info("Backtest %s: %d passed filter", target_date, len(screened))

    # Create a backtest_run record
    run_res = client.table("backtest_runs").insert({
        "run_date": target_date,
        "triggered_by": "backtest_script",
        "dart_used": False,
    }).execute()
    run_id = (run_res.data or [{}])[0].get("id")
    if not run_id:
        logger.error("Failed to create backtest_run record")
        return {"date": target_date, "screened": len(screened), "achieved_10x": 0, "hit_rate": 0.0}

    # Fetch stock names/markets for all tickers (screened + control group)
    all_tickers = list({s["ticker"] for s in scores})
    stock_res = client.table("stocks").select("ticker, name_kr, market").in_("ticker", all_tickers).execute()
    stock_meta = {r["ticker"]: r for r in (stock_res.data or [])}

    achieved_10x = 0
    batch_results = []
    future_date = (date.fromisoformat(target_date) + timedelta(days=1095)).isoformat()

    for s in screened:
        ticker = s["ticker"]
        meta = stock_meta.get(ticker, {})

        price_start = _get_price_on_date(ticker, target_date, meta.get("market", ""))
        price_end = _get_price_on_date(ticker, future_date, meta.get("market", ""))

        actual_x: float | None = None
        hit = False
        if price_start and price_end and price_start > 0:
            actual_x = round(price_end / price_start, 2)
            if actual_x >= 10:
                achieved_10x += 1
                hit = True

        # Build cats dict from score categories
        cats = {
            "growth": s.get("growth", 0),
            "momentum": s.get("momentum", 0),
            "quality": s.get("quality", 0),
            "sponsorship": s.get("sponsorship", 0),
            "value": s.get("value", 0),
            "safety": s.get("safety", 0),
            "size": s.get("size", 0),
        }
        scores_by_filter = s.get("scores_by_filter") or {}
        primary_cat = _derive_primary_rise_category(cats, scores_by_filter)

        batch_results.append({
            "run_id": run_id,
            "ticker": ticker,
            "name": meta.get("name_kr"),
            "market": meta.get("market"),
            "snapshot_date": target_date,
            "actual_x": actual_x,
            "score_10x": s.get("score_10x"),
            "passed": True,
            "failed_filters": [],
            "cats": {**cats, "primary_rise_category": primary_cat},
            "price_at_snapshot": price_start,
            "is_target": hit,
        })

    # Also save non-passing stocks as control group (sample: up to 50)
    non_screened = [s for s in scores if not s["passed"] or (s.get("score_10x") or 0) < 65][:50]
    for s in non_screened:
        ticker = s["ticker"]
        meta = stock_meta.get(ticker, {})
        batch_results.append({
            "run_id": run_id,
            "ticker": ticker,
            "name": meta.get("name_kr"),
            "market": meta.get("market"),
            "snapshot_date": target_date,
            "actual_x": None,
            "score_10x": s.get("score_10x"),
            "passed": s.get("passed", False),
            "failed_filters": s.get("failed_filters") or [],
            "cats": None,
            "price_at_snapshot": None,
            "is_target": False,
        })

    if batch_results:
        client.table("backtest_results").insert(batch_results).execute()
        logger.info("Saved %d backtest_results for run %s", len(batch_results), run_id)

    hit_rate = achieved_10x / len(screened) if screened else 0
    result = {
        "date": target_date,
        "screened": len(screened),
        "achieved_10x": achieved_10x,
        "hit_rate": round(hit_rate * 100, 1),
        "run_id": run_id,
    }
    logger.info("Backtest result: %s", result)
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run_backtest(BACKTEST_START)
    print(result)
