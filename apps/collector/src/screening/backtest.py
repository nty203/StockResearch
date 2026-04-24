"""Point-in-time backtest — validates filter/score against 2020-2024 history.

Uses:
  - FinanceDataReader for KR prices (includes delisted)
  - Stooq CSV for US prices (free, includes delisted)

Reports: hit rate of 10x screened stocks that actually achieved 10x.
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


def run_backtest(target_date: str = BACKTEST_START) -> dict:
    """Run point-in-time backtest for a specific date.

    Returns: {screened: int, achieved_10x: int, hit_rate: float}
    """
    client = get_client()
    res = client.table("screen_scores").select("ticker, passed, score_10x").eq("run_date", target_date).execute()
    scores = res.data or []

    screened = [s for s in scores if s["passed"] and (s.get("score_10x") or 0) >= 65]
    logger.info("Backtest %s: %d passed filter", target_date, len(screened))

    achieved_10x = 0
    for s in screened:
        ticker = s["ticker"]
        # Check if price 3 years later is >= 10x
        future_date = (
            date.fromisoformat(target_date) + timedelta(days=1095)
        ).isoformat()
        price_start = _get_price_on_date(ticker, target_date, "")
        price_end = _get_price_on_date(ticker, future_date, "")
        if price_start and price_end and price_end >= price_start * 10:
            achieved_10x += 1

    hit_rate = achieved_10x / len(screened) if screened else 0
    result = {
        "date": target_date,
        "screened": len(screened),
        "achieved_10x": achieved_10x,
        "hit_rate": round(hit_rate * 100, 1),
    }
    logger.info("Backtest result: %s", result)
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run_backtest(BACKTEST_START)
    print(result)
