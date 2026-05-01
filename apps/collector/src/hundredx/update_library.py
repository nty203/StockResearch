"""Update hundredx_library_stocks with current multiplier.

Concept: even if peak_multiplier was seeded at 8x, if the stock continues rising,
re-running this script weekly tracks the *current* multiplier from rise_start_date.
This implements "특정 주기 업데이트로 최종 100배 추종".

Logic per library stock:
  1. Fetch price_at_rise_start (closest available trading day to rise_start_date).
  2. Fetch latest close price.
  3. latest_multiplier = latest_close / price_at_rise_start.
  4. Update peak_multiplier = MAX(peak_multiplier, latest_multiplier).
  5. Stamp latest_updated_at.

Skips silently when price data is unavailable for the stock or rise_start_date is NULL.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone, timedelta

from ..upsert import get_client, pipeline_run

logger = logging.getLogger(__name__)


def _fetch_close_near_date(client, ticker: str, target_date: str, window_days: int = 14) -> float | None:
    """Get the closest trading-day close to target_date (forward up to window_days).

    If target_date is older than retained price history (prune_prices keeps 2 years),
    fall back to the OLDEST available price for the ticker. The resulting
    latest_multiplier becomes 'since earliest tracked price → today', which is still
    useful as a running tracker.
    """
    end = (datetime.fromisoformat(target_date) + timedelta(days=window_days)).date().isoformat()
    res = (
        client.table("prices_daily")
        .select("date, close")
        .eq("ticker", ticker)
        .gte("date", target_date)
        .lte("date", end)
        .order("date", desc=False)
        .limit(1)
        .execute()
    )
    rows = res.data or []
    if rows:
        return float(rows[0]["close"])

    # Fallback: oldest price available for this ticker
    res2 = (
        client.table("prices_daily")
        .select("date, close")
        .eq("ticker", ticker)
        .order("date", desc=False)
        .limit(1)
        .execute()
    )
    rows2 = res2.data or []
    return float(rows2[0]["close"]) if rows2 else None


def _fetch_latest_close(client, ticker: str) -> float | None:
    res = (
        client.table("prices_daily")
        .select("date, close")
        .eq("ticker", ticker)
        .order("date", desc=True)
        .limit(1)
        .execute()
    )
    rows = res.data or []
    return float(rows[0]["close"]) if rows else None


def run() -> int:
    """Recompute latest_multiplier for every library stock; bump peak if exceeded."""
    client = get_client()
    now_iso = datetime.now(timezone.utc).isoformat()
    updated = 0
    skipped = 0

    with pipeline_run(client, "hundredx") as (rows_out, _):
        lib_res = (
            client.table("hundredx_library_stocks")
            .select("id, ticker, rise_start_date, peak_multiplier, price_at_rise_start")
            .execute()
        )
        rows = lib_res.data or []
        logger.info("Processing %d library entries", len(rows))

        # Cache prices per ticker (multi-category rows share the same ticker)
        rise_price_cache: dict[tuple[str, str], float | None] = {}
        latest_price_cache: dict[str, float | None] = {}

        for row in rows:
            ticker = row["ticker"]
            rise_start = row.get("rise_start_date")
            if not rise_start:
                skipped += 1
                continue

            # rise-start price (cache by (ticker, date))
            cache_key = (ticker, rise_start)
            if cache_key not in rise_price_cache:
                stored = row.get("price_at_rise_start")
                rise_price_cache[cache_key] = (
                    float(stored) if stored is not None
                    else _fetch_close_near_date(client, ticker, rise_start)
                )
            rise_price = rise_price_cache[cache_key]

            # latest close
            if ticker not in latest_price_cache:
                latest_price_cache[ticker] = _fetch_latest_close(client, ticker)
            latest_price = latest_price_cache[ticker]

            if rise_price is None or latest_price is None or rise_price <= 0:
                skipped += 1
                continue

            latest_multiplier = round(latest_price / rise_price, 2)
            existing_peak = float(row.get("peak_multiplier") or 0.0)
            new_peak = max(existing_peak, latest_multiplier)

            try:
                client.table("hundredx_library_stocks").update({
                    "price_at_rise_start": rise_price,
                    "latest_multiplier": latest_multiplier,
                    "peak_multiplier": new_peak,
                    "latest_updated_at": now_iso,
                }).eq("id", row["id"]).execute()
                updated += 1
            except Exception as e:
                logger.warning("Update failed for %s/%s: %s", ticker, row.get("category"), e)
                skipped += 1

        logger.info("Library update: %d updated, %d skipped", updated, skipped)
        rows_out[0] = updated

    return updated


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    n = run()
    print(f"Done: {n} library entries updated")
