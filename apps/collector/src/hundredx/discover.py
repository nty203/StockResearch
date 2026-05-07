"""Step 1: Auto-discover 100x stocks from 5-year price history.

Algorithm:
  For each active KR stock:
    1. Fetch 5 years of daily close from FinanceDataReader
    2. For each (start, peak) pair, compute multiplier = peak.close / start.close
    3. Find the BEST multiplier within the window
    4. Determine rise_start_date: the date of the trough that preceded the peak
       (use max(close) and min(close before max_date))
    5. If multiplier >= min_multiplier, add to library

Output:
  - Auto-INSERT into hundredx_library_stocks (ON CONFLICT DO NOTHING)
  - Category left as '미분류' for stocks discovered this way; extract_signals.py fills later
  - Print report to stdout

Usage:
  uv run python -m src.hundredx.discover
  uv run python -m src.hundredx.discover --min-multiplier 50 --years 5
"""
from __future__ import annotations
import argparse
import logging
import os
from datetime import date, timedelta
from dataclasses import dataclass

import FinanceDataReader as fdr

from ..upsert import get_client, pipeline_run

logger = logging.getLogger(__name__)


@dataclass
class DiscoveredStock:
    ticker: str
    multiplier: float          # peak / trough
    trough_date: str           # rise_start_date candidate
    trough_price: float
    peak_date: str
    peak_price: float
    years_to_peak: float       # months between trough and peak


def _find_best_multiplier(prices: list[tuple[str, float]]) -> tuple[float, str, float, str, float]:
    """Given chronological [(date_str, close), ...], find best peak / preceding trough.

    Returns (multiplier, trough_date, trough_price, peak_date, peak_price).
    Algorithm: scan once tracking running min; for each price, multiplier = price / running_min.
    """
    if len(prices) < 2:
        return 0.0, "", 0.0, "", 0.0

    running_min_price = prices[0][1]
    running_min_date = prices[0][0]
    best_multiplier = 0.0
    best_trough_date = prices[0][0]
    best_trough_price = prices[0][1]
    best_peak_date = prices[0][0]
    best_peak_price = prices[0][1]

    for d, close in prices:
        if close <= 0:
            continue
        if running_min_price <= 0:
            running_min_price = close
            running_min_date = d
            continue
        m = close / running_min_price
        if m > best_multiplier:
            best_multiplier = m
            best_trough_date = running_min_date
            best_trough_price = running_min_price
            best_peak_date = d
            best_peak_price = close
        if close < running_min_price:
            running_min_price = close
            running_min_date = d

    return best_multiplier, best_trough_date, best_trough_price, best_peak_date, best_peak_price


def discover_for_ticker(ticker: str, years: int = 5) -> DiscoveredStock | None:
    """Fetch `years` years of prices and find best peak multiplier."""
    start = (date.today() - timedelta(days=int(years * 365.25))).isoformat()
    try:
        df = fdr.DataReader(ticker, start)
        if df.empty:
            return None
        df = df.reset_index().sort_values("Date")
        prices: list[tuple[str, float]] = [
            (str(r["Date"])[:10], float(r["Close"]))
            for _, r in df.iterrows()
            if r.get("Close") == r.get("Close") and float(r.get("Close", 0)) > 0
        ]
    except Exception as e:
        logger.debug("Fetch failed for %s: %s", ticker, e)
        return None

    if not prices:
        return None

    mult, trough_d, trough_p, peak_d, peak_p = _find_best_multiplier(prices)
    if mult < 2.0:  # below 2x not interesting
        return None

    # years between trough and peak
    try:
        from datetime import datetime as _dt
        td = _dt.fromisoformat(trough_d).date()
        pd_ = _dt.fromisoformat(peak_d).date()
        years_between = (pd_ - td).days / 365.25
    except Exception:
        years_between = 0.0

    return DiscoveredStock(
        ticker=ticker,
        multiplier=round(mult, 2),
        trough_date=trough_d,
        trough_price=round(trough_p, 2),
        peak_date=peak_d,
        peak_price=round(peak_p, 2),
        years_to_peak=round(years_between, 2),
    )


def run(years: int = 10, min_multiplier: float = 100.0,
        market_filter: str | None = None,
        auto_insert: bool = True) -> list[DiscoveredStock]:
    """Discover stocks that achieved >= min_multiplier within `years` years.

    Default window is 10 years to capture full cycle 100x cases (e.g. 셀트리온 80x took 8y).
    KR universe only — US stocks use yfinance in a separate path if needed.
    """
    client = get_client()

    # Load exclusion list
    exclude_path = os.path.join(os.path.dirname(__file__), "exclude.txt")
    exclude_tickers = set()
    if os.path.exists(exclude_path):
        with open(exclude_path, "r", encoding="utf-8") as f:
            for line in f:
                t = line.split("#")[0].strip()
                if t:
                    exclude_tickers.add(t)
        logger.info("Loaded %d excluded tickers", len(exclude_tickers))

    with pipeline_run(client, "hundredx") as (rows_out, _):
        # Fetch active KR universe (KOSPI + KOSDAQ only — 10y data via FinanceDataReader)
        kr_markets = ["KOSPI", "KOSDAQ"]
        if market_filter is not None:
            kr_markets = [market_filter] if market_filter in kr_markets else []
        res = (
            client.table("stocks")
            .select("ticker, market, name_kr, sector_tag")
            .eq("is_active", True)
            .in_("market", kr_markets)
            .execute()
        )
        stocks = res.data or []
        logger.info("Discovering across %d active KR stocks (%dy window, min %.0fx)",
                    len(stocks), years, min_multiplier)

        discovered: list[DiscoveredStock] = []
        for i, s in enumerate(stocks):
            ticker = s["ticker"]
            if ticker in exclude_tickers:
                continue
            if i % 100 == 0 and i > 0:
                logger.info("Progress: %d/%d (found %d so far)", i, len(stocks), len(discovered))
            result = discover_for_ticker(ticker, years=years)
            if result is None:
                continue
            if result.multiplier >= min_multiplier:
                discovered.append(result)

        discovered.sort(key=lambda d: d.multiplier, reverse=True)
        logger.info("Found %d stocks with >= %.0fx in %dy window", len(discovered), min_multiplier, years)

        # Auto-insert into hundredx_library_stocks
        if auto_insert and discovered:
            existing_res = (
                client.table("hundredx_library_stocks")
                .select("ticker, category")
                .execute()
            )
            existing_set = {(r["ticker"], r["category"]) for r in (existing_res.data or [])}

            new_rows = []
            for d in discovered:
                # Default category for auto-discovered: '미분류' (extract_signals.py reclassifies later)
                key = (d.ticker, "미분류")
                if key in existing_set:
                    continue
                # Skip if ticker already has any category (from manual seed)
                if any(t == d.ticker for (t, _) in existing_set):
                    continue
                new_rows.append({
                    "ticker": d.ticker,
                    "category": "미분류",
                    "rise_start_date": d.trough_date,
                    "earliest_signal_date": d.trough_date,
                    "peak_multiplier": d.multiplier,
                    "price_at_rise_start": d.trough_price,
                    "notes": (
                        f"자동 발견: {d.trough_date}({d.trough_price:.0f}) → "
                        f"{d.peak_date}({d.peak_price:.0f}) {d.multiplier:.1f}x "
                        f"({d.years_to_peak}년)"
                    ),
                })

            if new_rows:
                try:
                    client.table("hundredx_library_stocks").upsert(
                        new_rows, on_conflict="ticker,category"
                    ).execute()
                    logger.info("Auto-inserted %d new library entries", len(new_rows))
                except Exception as e:
                    logger.warning("Auto-insert failed: %s", e)

        rows_out[0] = len(discovered)
        return discovered


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--years", type=int, default=10,
                        help="Price history window in years (default 10 to capture full-cycle 100x)")
    parser.add_argument("--min-multiplier", type=float, default=100.0,
                        help="Min peak multiplier (e.g. 100 for true 100x, 30 for 30배+)")
    parser.add_argument("--market", choices=["KOSPI", "KOSDAQ"], default=None)
    parser.add_argument("--no-insert", action="store_true",
                        help="Print only, do not insert into library")
    args = parser.parse_args()

    results = run(
        years=args.years,
        min_multiplier=args.min_multiplier,
        market_filter=args.market,
        auto_insert=not args.no_insert,
    )
    print(f"\n=== Discovered {len(results)} stocks (>= {args.min_multiplier}x in {args.years}y) ===\n")
    for d in results[:30]:
        print(f"  {d.ticker:<8} {d.multiplier:>6.1f}x  "
              f"{d.trough_date} ({d.trough_price:>10,.0f}) -> "
              f"{d.peak_date} ({d.peak_price:>10,.0f})  "
              f"{d.years_to_peak}y")
