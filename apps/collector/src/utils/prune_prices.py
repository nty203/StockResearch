"""Prune prices_daily to keep only 2 years of data.

Run AFTER hundredx update_library completes (collect-weekly.yml sequential step).

Note: hundredx update_library uses prices for rise_start_date baseline. The
fallback in update_library handles missing historical prices gracefully (uses
oldest available), so pruning >2y data is safe.
"""
from __future__ import annotations
import logging
import os
from datetime import date, timedelta

from ..upsert import get_client

logger = logging.getLogger(__name__)

RETENTION_DAYS = 730
WINDOW_DAYS = int(os.environ.get("PRICE_PRUNE_WINDOW_DAYS", "7"))


def _delete_window(client, start: date, end: date) -> int:
    res = (
        client.table("prices_daily")
        .delete()
        .gte("date", start.isoformat())
        .lt("date", end.isoformat())
        .execute()
    )
    return len(res.data or [])


def _oldest_price_date(client, cutoff: str) -> date | None:
    res = (
        client.table("prices_daily")
        .select("date")
        .lt("date", cutoff)
        .order("date")
        .limit(1)
        .execute()
    )
    rows = res.data or []
    if not rows:
        return None
    return date.fromisoformat(str(rows[0]["date"])[:10])


def run() -> int:
    client = get_client()
    cutoff_date = date.today() - timedelta(days=RETENTION_DAYS)
    cutoff = cutoff_date.isoformat()

    start = _oldest_price_date(client, cutoff)
    if start is None:
        logger.info("No price rows older than %s", cutoff)
        return 0

    count = 0
    window_days = max(1, WINDOW_DAYS)
    while start < cutoff_date:
        end = min(start + timedelta(days=window_days), cutoff_date)
        try:
            count += _delete_window(client, start, end)
            logger.info("Pruned prices from %s to %s", start, end)
        except Exception as exc:
            if window_days == 1:
                raise
            logger.warning("Window prune failed for %s to %s: %s; retrying daily", start, end, exc)
            day = start
            while day < end:
                count += _delete_window(client, day, day + timedelta(days=1))
                day += timedelta(days=1)
        start = end
    logger.info("Pruned %d price rows older than %s", count, cutoff)
    return count


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
