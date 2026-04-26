"""News RSS collector — 한경, 조선비즈, Yahoo Finance."""
import logging
import re
import time
from datetime import datetime, timezone

import feedparser

from .upsert import get_client, upsert_batch, pipeline_run

logger = logging.getLogger(__name__)

RSS_FEEDS = [
    # Korean financial news
    ("https://www.hankyung.com/feed/finance", "ko"),
    ("https://biz.chosun.com/rcms/rss/3/1.xml", "ko"),
    # Yahoo Finance (market news)
    ("https://finance.yahoo.com/news/rssindex", "en"),
]


def _parse_date(entry) -> str:
    """Parse RSS date to ISO string."""
    published = entry.get("published_parsed") or entry.get("updated_parsed")
    if published:
        dt = datetime(*published[:6], tzinfo=timezone.utc)
        return dt.isoformat()
    return datetime.now(timezone.utc).isoformat()


def _find_ticker_mentions(text: str, ticker_set: set[str]) -> list[str]:
    """Find stock ticker mentions in article text."""
    # Korean: 6-digit codes
    kr = set(re.findall(r"\b(\d{6})\b", text)) & ticker_set
    # US: uppercase words 1-5 chars
    us = set(re.findall(r"\b([A-Z]{1,5})\b", text)) & ticker_set
    return list(kr | us)


def collect_rss_news(ticker_set: set[str]) -> list[dict]:
    rows = []
    for feed_url, lang in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries:
                title = entry.get("title", "")
                summary = entry.get("summary", entry.get("description", ""))
                full_text = f"{title} {summary}"
                tickers = _find_ticker_mentions(full_text, ticker_set)
                if not tickers:
                    continue
                published = _parse_date(entry)
                url = entry.get("link", "")
                for ticker in tickers:
                    rows.append({
                        "ticker": ticker,
                        "source": feed.feed.get("title", feed_url)[:50],
                        "published_at": published,
                        "url": url,
                        "title": title[:500],
                        "summary": summary[:1000] if summary else None,
                        "lang": lang,
                    })
        except Exception as e:
            logger.warning("RSS feed error %s: %s", feed_url, e)
        time.sleep(0.5)
    return rows


def run() -> int:
    client = get_client()
    res = client.table("stocks").select("ticker").eq("is_active", True).execute()
    ticker_set = {r["ticker"] for r in (res.data or [])}

    rows = collect_rss_news(ticker_set)
    with pipeline_run(client, "news") as (rows_out, _):
        count = upsert_batch(client, "news", rows, on_conflict="ticker,url")
        rows_out[0] = count
    logger.info("News upserted %d rows", count)
    return count


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
