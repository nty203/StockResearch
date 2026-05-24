"""filings.raw_text 가 비어있는 공시들의 본문을 DART API로 backfill.

우선순위:
  1. 라이브러리 100배 종목의 rise_start 이전 N일 구간 (평가용)
  2. 최근 30일 active 매치들의 evidence filings
  3. 그 외

CLI:
    python -m src.hundredx.backfill_filing_bodies --library-only --lookback-days 365
    python -m src.hundredx.backfill_filing_bodies --max 500
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from datetime import date, datetime, timedelta

logger = logging.getLogger(__name__)


def _safe_date(v) -> date | None:
    if not v:
        return None
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def find_library_filings(client, lookback_days: int = 365) -> list[dict]:
    """라이브러리 종목의 rise_start_date 이전 N일 구간 + 빈 raw_text 인 filings."""
    lib = (
        client.table("hundredx_library_stocks")
        .select("ticker, rise_start_date")
        .gte("rise_start_date", "2021-01-01")
        .execute()
        .data or []
    )
    targets = []
    for s in lib:
        rd = _safe_date(s.get("rise_start_date"))
        if rd is None:
            continue
        lo = (rd - timedelta(days=lookback_days)).isoformat()
        hi = rd.isoformat()
        rows = (
            client.table("filings")
            .select("id, ticker, url, raw_text, filed_at, headline")
            .eq("ticker", s["ticker"])
            .gte("filed_at", lo)
            .lte("filed_at", hi)
            .or_("raw_text.is.null,raw_text.eq.")
            .order("filed_at", desc=True)
            .limit(200)
            .execute()
            .data or []
        )
        targets.extend(rows)
    # dedupe by id
    by_id = {r["id"]: r for r in targets}
    return list(by_id.values())


def find_recent_empty_filings(client, days: int = 90, limit: int = 1000) -> list[dict]:
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    rows = (
        client.table("filings")
        .select("id, ticker, url, raw_text, filed_at, headline")
        .gte("filed_at", cutoff)
        .or_("raw_text.is.null")
        .order("filed_at", desc=True)
        .limit(limit)
        .execute()
        .data or []
    )
    return rows


def backfill(client, filings: list[dict], dry_run: bool = False) -> dict:
    from ..utils.dart_body import extract_rcept_no, fetch_body

    counts = {"total": len(filings), "no_rcept": 0, "fetched": 0, "empty_body": 0, "saved": 0, "err": 0}
    for i, f in enumerate(filings):
        rno = extract_rcept_no(f.get("url"))
        if not rno:
            counts["no_rcept"] += 1
            continue
        try:
            body = fetch_body(rno)
        except Exception as exc:
            logger.warning("fetch error %s: %s", rno, exc)
            counts["err"] += 1
            continue
        if not body:
            counts["empty_body"] += 1
            continue
        counts["fetched"] += 1
        if not dry_run:
            try:
                client.table("filings").update({"raw_text": body}).eq("id", f["id"]).execute()
                counts["saved"] += 1
            except Exception as exc:
                logger.warning("update error %s: %s", f["id"], exc)
                counts["err"] += 1
        time.sleep(0.1)  # DART rate limit 안전 마진
        if (i + 1) % 25 == 0:
            logger.info(
                "Progress %d/%d  saved=%d fetched=%d empty=%d no_rcept=%d err=%d",
                i + 1, len(filings),
                counts["saved"], counts["fetched"], counts["empty_body"], counts["no_rcept"], counts["err"],
            )
    return counts


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass

    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    p = argparse.ArgumentParser()
    p.add_argument("--library-only", action="store_true",
                   help="라이브러리 종목 pre-rise 구간만 backfill")
    p.add_argument("--lookback-days", type=int, default=365,
                   help="라이브러리 종목 rise_start 이전 몇 일까지 fetch (기본 365)")
    p.add_argument("--max", type=int, default=None, help="처리할 최대 건수")
    p.add_argument("--dry-run", action="store_true", help="DB write 없이 fetch만")
    args = p.parse_args()

    from ..upsert import get_client
    client = get_client()

    if args.library_only:
        filings = find_library_filings(client, lookback_days=args.lookback_days)
        logger.info("Library backfill target: %d filings", len(filings))
    else:
        filings = find_recent_empty_filings(client)
        logger.info("Recent backfill target: %d filings", len(filings))

    if args.max:
        filings = filings[: args.max]
        logger.info("Limited to %d", len(filings))

    counts = backfill(client, filings, dry_run=args.dry_run)
    logger.info("=== Done === %s", counts)


if __name__ == "__main__":
    main()
