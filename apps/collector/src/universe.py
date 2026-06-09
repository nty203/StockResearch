"""Universe collector — KOSPI+KOSDAQ+S&P1500 stock universe."""
import logging
import os

import FinanceDataReader as fdr
import pandas as pd

from .upsert import get_client, upsert_batch, pipeline_run

logger = logging.getLogger(__name__)

SP1500_INDEXES = ["S&P500", "S&P400", "S&P600"]


KOSPI_ACTIVE_LIMIT = None   # None = 전체 활성, 숫자 = 시총 상위 N개만 is_active=True
KOSDAQ_ACTIVE_LIMIT = None  # None = 전체 활성


def collect_kr_universe() -> list[dict]:
    """Fetch KOSPI + KOSDAQ tickers from KRX. All stocks are active by default."""
    rows = []
    
    # Attempt to fetch KOSPI and KOSDAQ from KRX-DESC as fallback if primary fails
    df_desc = None
    use_desc = False
    try:
        # Check if primary KRX works (often blocked by WAF for foreign IPs or KRX down)
        fdr.StockListing("KOSPI")
    except Exception as e:
        logger.warning("Primary KRX fetch failed, falling back to KRX-DESC: %s", e)
        use_desc = True

    if use_desc:
        try:
            df_desc = fdr.StockListing("KRX-DESC")
        except Exception as e2:
            logger.warning("FDR KRX-DESC fallback failed: %s. Fetching cache from GitHub directly...", e2)
            try:
                import urllib.request
                import json
                # Get the latest cache file from the GitHub repository metadata
                api_url = "https://api.github.com/repos/FinanceData/fdr_krx_data_cache/contents/data/listing/desc"
                req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req) as response:
                    files = json.loads(response.read().decode("utf-8"))
                csv_files = [f for f in files if f["name"].endswith(".csv")]
                if csv_files:
                    csv_files.sort(key=lambda x: x["name"])
                    latest_csv_url = csv_files[-1]["download_url"]
                    logger.info("Loading latest desc file directly: %s", latest_csv_url)
                    df_desc = pd.read_csv(latest_csv_url, dtype={"Code": str})
            except Exception as github_err:
                logger.error("Failed to fetch directly from GitHub cache: %s", github_err)
                df_desc = None
    
    for market in ("KOSPI", "KOSDAQ"):
        if use_desc and df_desc is not None:
            # Map market strings: KOSDAQ GLOBAL is also KOSDAQ
            mask = df_desc["Market"].str.contains(market, na=False, case=False)
            df = df_desc[mask].copy()
            marcap_col = None
        else:
            try:
                df = fdr.StockListing(market)
            except Exception as e3:
                logger.warning("Failed to fetch %s listing: %s. Trying hardcoded GitHub cache direct fetch...", market, e3)
                try:
                    import urllib.request
                    import json
                    api_url = "https://api.github.com/repos/FinanceData/fdr_krx_data_cache/contents/data/listing/krx"
                    req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req) as response:
                        files = json.loads(response.read().decode("utf-8"))
                    csv_files = [f for f in files if f["name"].endswith(".csv")]
                    if csv_files:
                        csv_files.sort(key=lambda x: x["name"])
                        latest_csv_url = csv_files[-1]["download_url"]
                        logger.info("Loading latest krx file directly: %s", latest_csv_url)
                        df_full = pd.read_csv(latest_csv_url, dtype={'Code': str, 'Dept': str, 'ChangeCode': str, 'MarketId': str})
                        mkt_map = {'KOSPI': 'STK', 'KOSDAQ': 'KSQ'}
                        df = df_full[df_full['MarketId'] == mkt_map[market]].reset_index(drop=True)
                    else:
                        raise ValueError("No files found")
                except Exception as e4:
                    logger.error("All listing fallback systems failed for %s: %s", market, e4)
                    continue
            
            # Sort by market cap descending (Marcap column, may be 0 if unavailable)
            marcap_col = next((c for c in df.columns if c.lower() in ("marcap", "mktcap", "market_cap", "시가총액")), None)
            if marcap_col:
                df = df.sort_values(marcap_col, ascending=False).reset_index(drop=True)
                
        limit = KOSPI_ACTIVE_LIMIT if market == "KOSPI" else KOSDAQ_ACTIVE_LIMIT

        for idx, r in df.iterrows():
            ticker = str(r.get("Code", r.get("Symbol", ""))).strip()
            if not ticker:
                continue
            
            row_dict = {
                "ticker": ticker,
                "market": market,
                "name_kr": str(r.get("Name", r.get("Sector", ""))),
                "name_en": None,
                "sector_wics": str(r.get("Sector", r.get("Industry", ""))),
                "industry": str(r.get("Industry", "")),
                "is_active": True if limit is None else (idx < limit),
            }
            
            # Only include market_cap if it exists; otherwise Supabase upsert ignores it
            if marcap_col:
                marcap_raw = r.get(marcap_col)
                try:
                    market_cap_val = int(marcap_raw) if marcap_raw and float(marcap_raw) > 0 else None
                except (TypeError, ValueError):
                    market_cap_val = None
                row_dict["market_cap"] = market_cap_val
                
            rows.append(row_dict)
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
