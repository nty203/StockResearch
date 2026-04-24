"""Prune prices_daily to keep only 2 years of data.

Run AFTER backtest completes (collect-weekly.yml sequential step).
"""
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
