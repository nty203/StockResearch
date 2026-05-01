"""Prune prices_daily to keep only 2 years of data.

Run AFTER hundredx update_library completes (collect-weekly.yml sequential step).

Note: hundredx update_library uses prices for rise_start_date baseline. The
fallback in update_library handles missing historical prices gracefully (uses
oldest available), so pruning >2y data is safe.
"""
from __future__ import annotations
import logging
from datetime import date, timedelta

from ..upsert import get_client

logger = logging.getLogger(__name__)

RETENTION_DAYS = 730


def run() -> int:
    client = get_client()
    cutoff = (date.today() - timedelta(days=RETENTION_DAYS)).isoformat()

    res = client.table("prices_daily").delete().lt("date", cutoff).execute()
    count = len(res.data or [])
    logger.info("Pruned %d price rows older than %s", count, cutoff)
    return count


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
