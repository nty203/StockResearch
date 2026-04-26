"""Universe collector — KOSPI+KOSDAQ+S&P1500 stock universe."""
import logging
import os

import FinanceDataReader as fdr
import pandas as pd

from .upsert import get_client, upsert_batch, pipeline_run

logger = logging.getLogger(__name__)

SP1500_INDEXES = ["S&P500", "S&P400", "S&P600"]


KOSPI_ACTIVE_LIMIT = 100   # 시총 상위 N개만 is_active=True
KOSDAQ_ACTIVE_LIMIT = 0    # 0 = 전체 비활성 (나중에 필요시 확장)


def collect_kr_universe() -> list[dict]:
    """Fetch KOSPI + KOSDAQ tickers from KRX. Only top-N by market cap are active."""
    rows = []
    for market in ("KOSPI", "KOSDAQ"):
        df = fdr.StockListing(market)
        # Sort by market cap descending (Marcap column, may be 0 if unavailable)
        marcap_col = next((c for c in df.columns if c.lower() in ("marcap", "mktcap", "market_cap", "시가총액")), None)
        if marcap_col:
            df = df.sort_values(marcap_col, ascending=False).reset_index(drop=True)
        limit = KOSPI_ACTIVE_LIMIT if market == "KOSPI" else KOSDAQ_ACTIVE_LIMIT
        active_set = set(range(limit)) if limit > 0 else set()

        for idx, r in df.iterrows():
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
                "is_active": idx in active_set,
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
    seen: dict[str, dict] = {}
    for r in rows:
        seen[r["ticker"]] = r
    unique = list(seen.values())
    with pipeline_run(client, "universe") as (rows_out, _):
        count = upsert_batch(client, "stocks", unique, on_conflict="ticker,market")
        rows_out[0] = count
    logger.info("Universe upserted %d rows", count)
    return count


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
