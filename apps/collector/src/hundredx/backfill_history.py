"""Historical data backfill for library stocks.

For each library entry with rise_start_date set:
  1. Fetch DART filings in (rise_start - 18mo, rise_start + 3mo) via dart.list(corp=..., kind="A,B")
  2. Insert raw filing rows (headline only, no raw_text fetch — too expensive for backfill)
  3. extract_signals.py picks them up next run

Notes:
  - We only fetch headline + filed_at (raw_text body fetch via dart.document() is too slow
    for backfill — would be 1000s of API calls). Keyword detection works on headline alone
    for B-type 주요사항보고서 (수주, MOU, 증설, etc.).
  - Each call to dart.list(corp=...) is 1 API call. 15 library stocks × 1 = 15 calls. Cheap.
  - Skips stocks that already have filings in the target window.

Usage:
  uv run python -m src.hundredx.backfill_history
  uv run python -m src.hundredx.backfill_history --ticker 086520
"""
from __future__ import annotations
import argparse
import logging
import os
import re
from datetime import datetime, timedelta

import OpenDartReader as DartReader

from ..upsert import get_client, upsert_batch, pipeline_run
from ..filings_watch import KEYWORDS_KR, _extract_amount, _match_keywords

logger = logging.getLogger(__name__)


def _existing_filings_count(client, ticker: str, start: str, end: str) -> int:
    res = (
        client.table("filings")
        .select("id", count="exact")
        .eq("ticker", ticker)
        .gte("filed_at", start)
        .lt("filed_at", end)
        .limit(1)
        .execute()
    )
    return getattr(res, "count", 0) or 0


def backfill_for_library_stock(client, dart, ticker: str, rise_start: str,
                                months_before: int = 18, months_after: int = 3) -> int:
    """Fetch DART filings for one stock around rise_start_date. Returns rows inserted."""
    rise_dt = datetime.fromisoformat(rise_start)
    start_dt = rise_dt - timedelta(days=int(months_before * 30.5))
    end_dt = rise_dt + timedelta(days=int(months_after * 30.5))

    start_str = start_dt.date().isoformat()
    end_str = end_dt.date().isoformat()

    # Skip if already backfilled (any filings in window)
    existing = _existing_filings_count(client, ticker, start_str, end_str)
    if existing > 0:
        logger.info("Skip %s: %d filings already in window %s ~ %s",
                    ticker, existing, start_str, end_str)
        return 0

    rows = []
    # DART list with corp_code filter for this ticker
    try:
        # kind="B" = 주요사항보고서 (수주/M&A/증자 등) — 가장 정보량 높은 카테고리
        # Add "A" for 정기공시 (사업보고서 등) as well
        df = dart.list(corp=ticker, start=start_str.replace("-", ""),
                       end=end_str.replace("-", ""), kind="B")
        if df is None or df.empty:
            logger.info("%s: no filings in window", ticker)
            return 0

        for _, r in df.iterrows():
            headline = str(r.get("report_nm", ""))
            if not headline:
                continue
            filed_at_raw = str(r.get("rcept_dt", ""))
            if not filed_at_raw or len(filed_at_raw) < 8:
                continue
            # Format YYYYMMDD → YYYY-MM-DD
            filed_at = f"{filed_at_raw[:4]}-{filed_at_raw[4:6]}-{filed_at_raw[6:8]}T00:00:00"

            matched = _match_keywords(headline, KEYWORDS_KR)
            amount = _extract_amount(headline)
            rcept_no = str(r.get("rcept_no", ""))

            rows.append({
                "ticker": ticker,
                "source": "DART",
                "filing_type": str(r.get("report_nm", ""))[:50],
                "filed_at": filed_at,
                "url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}",
                "headline": headline,
                "raw_text": None,  # Skipped for backfill speed
                "keywords": matched,
                "parsed_amount": amount,
                "parsed_customer": None,
            })
    except Exception as e:
        logger.warning("DART fetch failed for %s: %s", ticker, e)
        return 0

    if not rows:
        return 0
    inserted = upsert_batch(client, "filings", rows, on_conflict="ticker,url")
    logger.info("%s: backfilled %d filings (%s ~ %s)", ticker, inserted, start_str, end_str)
    return inserted


def run(ticker_filter: str | None = None) -> int:
    api_key = os.environ.get("DART_API_KEY", "")
    if not api_key:
        logger.error("DART_API_KEY not set — backfill cannot run")
        return 0

    client = get_client()
    dart = DartReader(api_key)

    with pipeline_run(client, "hundredx") as (rows_out, _):
        q = client.table("hundredx_library_stocks").select("id, ticker, rise_start_date")
        if ticker_filter:
            q = q.eq("ticker", ticker_filter)
        rows = q.execute().data or []

        # Dedupe by ticker (multi-category rows share the same window)
        seen: set[str] = set()
        unique_targets: list[tuple[str, str]] = []
        for r in rows:
            t = r["ticker"]
            rs = r.get("rise_start_date")
            if t in seen or not rs:
                continue
            seen.add(t)
            unique_targets.append((t, rs))

        logger.info("Backfilling %d unique library stocks", len(unique_targets))

        total = 0
        for ticker, rise_start in unique_targets:
            n = backfill_for_library_stock(client, dart, ticker, rise_start)
            total += n

        rows_out[0] = total
        return total


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", help="Backfill only this ticker")
    args = parser.parse_args()
    n = run(ticker_filter=args.ticker)
    print(f"Done: {n} historical filings backfilled")
