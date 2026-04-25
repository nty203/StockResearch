"""Universe collector — KOSPI+KOSDAQ+S&P1500 stock universe."""
import logging
import os

import FinanceDataReader as fdr
import pandas as pd

from .upsert import get_client, upsert_batch

logger = logging.getLogger(__name__)

SP1500_INDEXES = ["S&P500", "S&P400", "S&P600"]


def collect_kr_universe() -> list[dict]:
    """Fetch KOSPI + KOSDAQ tickers from KRX."""
    rows = []
    for market in ("KOSPI", "KOSDAQ"):
        df = fdr.StockListing(market)
        for _, r in df.iterrows():
            ticker = str(r.get("Code", r.get("Symbol", ""))).strip()
            if not ticker:
                continue
            rows.append({
                "ticker": ticker,
                "market": market,
                "name_kr": str(r.get("Name", r.get("Sector", ""))),
                "name_en": None,
                "sector_wics": str(r.get("Sector", r.get("Industry", ""))),
                "industry": str(r.get("Industry", "")),
                "is_active": True,
            })
    return rows


def collect_us_universe() -> list[dict]:
    """Fetch S&P 500/400/600 tickers via FinanceDataReader."""
    rows = []
    for idx in SP1500_INDEXES:
        try:
            df = fdr.StockListing(idx)
        except Exception as e:
            logger.warning("Failed to fetch %s: %s", idx, e)
            continue
        for _, r in df.iterrows():
            ticker = str(r.get("Symbol", r.get("Code", ""))).strip()
            if not ticker:
                continue
            market = "NYSE" if r.get("Exchange", "").upper() in ("NYSE", "N") else "NASDAQ"
            rows.append({
                "ticker": ticker,
                "market": market,
                "name_kr": None,
                "name_en": str(r.get("Name", r.get("Longname", ""))),
                "sector_wics": str(r.get("Sector", "")),
                "industry": str(r.get("Industry", r.get("Subindustry", ""))),
                "is_active": True,
            })
    return rows


def run() -> int:
    client = get_client()
    rows = collect_kr_universe() + collect_us_universe()
    if not rows:
        logger.warning("No universe rows collected")
        return 0
    # Deduplicate by ticker (keep last)
    seen: dict[str, dict] = {}
    for r in rows:
        seen[r["ticker"]] = r
    unique = list(seen.values())
    count = upsert_batch(client, "stocks", unique, on_conflict="ticker,market")
    logger.info("Universe upserted %d rows", count)
    return count


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
