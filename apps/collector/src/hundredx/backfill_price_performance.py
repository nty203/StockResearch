"""One-shot backfill: populate NULL price_performance columns for active category matches.

Run after scanner has been upgraded to save price data.
This script fills historical gaps for the 26,000+ matches that currently have NULL values.

Usage:
    uv run python src/hundredx/backfill_price_performance.py
    uv run python src/hundredx/backfill_price_performance.py --dry-run
    uv run python src/hundredx/backfill_price_performance.py --limit 500
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

BATCH_SIZE = 50  # Update DB in batches to avoid timeouts
PRICE_PERFORMANCE_YEARS = 3


def run(client=None, dry_run: bool = False, limit: int = 5000) -> dict:
    """Backfill price_performance for active matches with NULL price data."""
    if client is None:
        from supabase import create_client
        from dotenv import load_dotenv
        load_dotenv()
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_SERVICE_KEY"]
        client = create_client(url, key)

    from .price_performance import fetch_window_performance

    now = datetime.now(timezone.utc)

    # 1. Fetch active matches with NULL price_performance
    logger.info("Fetching active matches with NULL price data...")
    res = (
        client.table("hundredx_category_matches")
        .select(
            "ticker, category, first_detected_at, "
            "price_baseline_date, price_current_multiplier"
        )
        .is_("exited_at", "null")
        .is_("price_current_multiplier", "null")
        .order("first_detected_at", desc=False)
        .limit(limit)
        .execute()
    )
    matches = res.data or []
    logger.info(f"Found {len(matches)} active matches with NULL price data")

    if not matches:
        return {"updated": 0, "skipped": 0, "total": 0}

    # 2. Fetch market info for all relevant tickers
    tickers = list({m["ticker"] for m in matches})
    stocks_res = (
        client.table("stocks")
        .select("ticker, market")
        .in_("ticker", tickers[:500])
        .execute()
    )
    market_by_ticker: dict[str, str | None] = {
        r["ticker"]: r.get("market")
        for r in (stocks_res.data or [])
    }

    # 3. Fetch + compute price performance per ticker (cached)
    perf_cache: dict[str, object] = {}
    updated = 0
    skipped = 0
    update_rows: list[dict] = []

    for i, m in enumerate(matches):
        ticker = m["ticker"]
        if ticker not in perf_cache:
            try:
                perf = fetch_window_performance(
                    ticker,
                    market=market_by_ticker.get(ticker),
                    years=PRICE_PERFORMANCE_YEARS,
                )
                perf_cache[ticker] = perf
            except Exception as e:
                logger.warning(f"price fetch failed for {ticker}: {e}")
                perf_cache[ticker] = None

        perf = perf_cache[ticker]
        if perf is None:
            skipped += 1
            continue

        update_rows.append({
            "ticker": ticker,
            "category": m["category"],
            "price_baseline_date": perf.baseline_date,
            "price_baseline_close": perf.baseline_close,
            "price_latest_date": perf.latest_date,
            "price_latest_close": perf.latest_close,
            "price_peak_date": perf.peak_date,
            "price_peak_close": perf.peak_close,
            "price_current_multiplier": perf.current_multiplier,
            "price_change_pct": perf.current_return_pct,
            "price_peak_multiplier": perf.peak_multiplier,
            "price_peak_change_pct": perf.peak_return_pct,
            "price_performance_updated_at": now.isoformat(),
        })

        if len(update_rows) >= BATCH_SIZE:
            if not dry_run:
                _flush_updates(client, update_rows)
                updated += len(update_rows)
            else:
                logger.info(f"[dry-run] Would update {len(update_rows)} rows")
                updated += len(update_rows)
            update_rows = []

        if (i + 1) % 200 == 0:
            logger.info(f"Progress: {i+1}/{len(matches)} processed, {updated} updated, {skipped} skipped")

    # Flush remaining
    if update_rows:
        if not dry_run:
            _flush_updates(client, update_rows)
            updated += len(update_rows)
        else:
            logger.info(f"[dry-run] Would update {len(update_rows)} rows")
            updated += len(update_rows)

    logger.info(f"Backfill complete: {updated} updated, {skipped} skipped (out of {len(matches)} total)")
    return {"updated": updated, "skipped": skipped, "total": len(matches)}


def _flush_updates(client, rows: list[dict]) -> None:
    """Upsert a batch of price performance updates."""
    try:
        client.table("hundredx_category_matches").upsert(
            rows, on_conflict="ticker,category"
        ).execute()
    except Exception as e:
        logger.warning(f"Batch upsert failed: {e}")
        # Try one by one
        for row in rows:
            try:
                client.table("hundredx_category_matches").update({
                    k: v for k, v in row.items() if k not in ("ticker", "category")
                }).eq("ticker", row["ticker"]).eq("category", row["category"]).execute()
            except Exception as e2:
                logger.warning(f"Single update failed for {row['ticker']}/{row['category']}: {e2}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    parser = argparse.ArgumentParser(description="Backfill price performance for NULL matches")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be updated, don't write")
    parser.add_argument("--limit", type=int, default=5000, help="Max matches to process")
    args = parser.parse_args()

    result = run(dry_run=args.dry_run, limit=args.limit)
    print(f"\nResult: {result}")
