"""Data coverage audit for PPTR scans.

This does not crawl the web. It reports whether the local Supabase data is fresh
enough to trust an "A-grade PPTR = 0" conclusion.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from dotenv import load_dotenv

load_dotenv()

from ..upsert import get_client


def _count(client, table: str, query_fn=None) -> int:
    query = client.table(table).select("*", count="exact")
    if query_fn:
        query = query_fn(query)
    res = query.limit(1).execute()
    return int(res.count or 0)


def _latest_date(client, table: str, column: str) -> str | None:
    rows = (
        client.table(table)
        .select(column)
        .order(column, desc=True)
        .limit(1)
        .execute()
        .data
        or []
    )
    return rows[0].get(column) if rows else None


def collect_coverage(client=None) -> dict:
    client = client or get_client()
    today = date.today()
    d30 = (today - timedelta(days=30)).isoformat()
    d90 = (today - timedelta(days=90)).isoformat()
    d730 = (today - timedelta(days=730)).isoformat()

    active_kr = _count(
        client,
        "stocks",
        lambda q: q.eq("is_active", True).in_("market", ["KOSPI", "KOSDAQ"]),
    )
    active_us = _count(
        client,
        "stocks",
        lambda q: q.eq("is_active", True).in_("market", ["NYSE", "NASDAQ"]),
    )
    filings_90d = _count(client, "filings", lambda q: q.gte("filed_at", d90))
    filings_2y = _count(client, "filings", lambda q: q.gte("filed_at", d730))
    filings_raw_text_2y = _count(
        client,
        "filings",
        lambda q: q.gte("filed_at", d730).not_.is_("raw_text", "null"),
    )
    news_30d = _count(client, "news", lambda q: q.gte("published_at", d30))
    pptr_rules = _count(client, "pptr_rules")
    pptr_matches = _count(client, "pptr_rule_matches")
    pptr_near_misses = _count(client, "pptr_rule_near_misses")

    return {
        "active_kr_stocks": active_kr,
        "active_us_stocks": active_us,
        "pptr_rules": pptr_rules,
        "pptr_rule_matches": pptr_matches,
        "pptr_rule_near_misses": pptr_near_misses,
        "filings_90d": filings_90d,
        "filings_2y": filings_2y,
        "filings_raw_text_2y": filings_raw_text_2y,
        "filings_raw_text_2y_pct": round(filings_raw_text_2y / filings_2y * 100, 2) if filings_2y else 0.0,
        "news_30d": news_30d,
        "latest_filing_at": _latest_date(client, "filings", "filed_at"),
        "latest_news_at": _latest_date(client, "news", "published_at"),
        "latest_price_date": _latest_date(client, "prices_daily", "date"),
        "caveat": (
            "PPTR scans are only as complete as collected filings/news. "
            "If filings/news are stale or raw_text coverage is low, report scope as current DB data."
        ),
    }


def run() -> dict:
    coverage = collect_coverage()
    print(json.dumps(coverage, ensure_ascii=False, indent=2, sort_keys=True))
    return coverage


if __name__ == "__main__":
    run()
