"""News RSS collector — 한경, 조선비즈, Yahoo Finance."""
import logging
import re
import time
from datetime import datetime, timezone

import feedparser

from .upsert import get_client, upsert_batch, pipeline_run, retry_execute

logger = logging.getLogger(__name__)

RSS_FEEDS = [
    # Korean financial news
    ("https://www.hankyung.com/feed/finance", "ko"),
    ("https://biz.chosun.com/rcms/rss/3/1.xml", "ko"),
    # Naver News — economy/finance section (증권·금융 뉴스 포함)
    ("https://news.naver.com/rss/main/NEWS_OFFICIAL_GROUP_003.xml", "ko"),
    # Maeil Business (매일경제)
    ("https://www.mk.co.kr/rss/30100041/", "ko"),      # 매경 증권
    ("https://www.mk.co.kr/rss/50300009/", "ko"),      # 매경 기업/경영
    # Yahoo Finance (market news)
    ("https://finance.yahoo.com/news/rssindex", "en"),
]


def normalize_title(title: str) -> str:
    """Normalize news title to strip spaces, special characters, and bracket contents."""
    if not title:
        return ""
    # Remove contents inside bracket-like characters, e.g. [단독], (종합), [특징주]
    t = re.sub(r"\[[^\]]*\]", "", title)
    t = re.sub(r"\([^)]*\)", "", t)
    # Remove special characters
    t = re.sub(r"[^\w\s]", "", t)
    # Strip spaces and lowercase
    t = "".join(t.split()).lower()
    return t


def _parse_date(entry) -> str:
    """Parse RSS date to ISO string."""
    published = entry.get("published_parsed") or entry.get("updated_parsed")
    if published:
        dt = datetime(*published[:6], tzinfo=timezone.utc)
        return dt.isoformat()
    return datetime.now(timezone.utc).isoformat()


def _build_mention_map(stocks: list[dict]) -> dict[str, str]:
    """Build mention token -> ticker map from tickers and company names."""
    mention_map: dict[str, str] = {}
    for stock in stocks:
        ticker = stock.get("ticker")
        if not ticker:
            continue
        values = [
            ticker,
            stock.get("name_kr"),
            stock.get("name_en"),
        ]
        for value in values:
            token = str(value or "").strip()
            if len(token) < 2:
                continue
            mention_map[token.lower()] = ticker
    return mention_map


def _find_ticker_mentions(text: str, ticker_set: set[str], mention_map: dict[str, str] | None = None) -> list[str]:
    """Find stock ticker mentions in article text."""
    mention_map = mention_map or {}
    # Korean: 6-digit codes
    kr = set(re.findall(r"\b(\d{6})\b", text)) & ticker_set
    # US: uppercase words 1-5 chars
    us = set(re.findall(r"\b([A-Z]{1,5})\b", text)) & ticker_set
    by_name = {
        ticker
        for token, ticker in mention_map.items()
        if token in text.lower()
    }
    return list(kr | us | by_name)


_RSS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; StockResearch/1.0; +https://github.com/nty203/StockResearch)",
    "Accept": "application/rss+xml, application/atom+xml, text/xml, */*",
    "Accept-Encoding": "gzip, deflate",
}


def _parse_feed_with_retry(feed_url: str, max_retries: int = 3) -> object:
    """feedparser.parse with User-Agent and retry logic."""
    import socket
    for attempt in range(max_retries):
        try:
            feed = feedparser.parse(
                feed_url,
                agent=_RSS_HEADERS["User-Agent"],
                request_headers=_RSS_HEADERS,
            )
            if feed.bozo and feed.bozo_exception and not feed.entries:
                raise feed.bozo_exception
            return feed
        except (OSError, socket.timeout) as e:
            if attempt < max_retries - 1:
                wait = 2.0 * (attempt + 1)
                logger.warning("RSS fetch error %s: %s (retry %d in %.1fs)", feed_url, e, attempt + 1, wait)
                time.sleep(wait)
        except Exception as e:
            logger.warning("RSS non-retryable error %s: %s", feed_url, e)
            break
    return feedparser.FeedParserDict()


def collect_rss_news(ticker_set: set[str], mention_map: dict[str, str] | None = None) -> list[dict]:
    rows = []
    seen_normalized_titles = set()
    for feed_url, lang in RSS_FEEDS:
        try:
            feed = _parse_feed_with_retry(feed_url)
            for entry in feed.entries:
                title = entry.get("title", "")
                norm_title = normalize_title(title)
                if norm_title:
                    if norm_title in seen_normalized_titles:
                        logger.info("Skipped duplicate RSS news title: %s", title)
                        continue
                    seen_normalized_titles.add(norm_title)

                summary = entry.get("summary", entry.get("description", ""))
                full_text = f"{title} {summary}"
                tickers = _find_ticker_mentions(full_text, ticker_set, mention_map)
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
    try:
        res = retry_execute(
            lambda: client.table("stocks")
            .select("ticker, name_kr, name_en")
            .eq("is_active", True)
            .execute()
        )
        stocks = res.data or []
        ticker_set = {r["ticker"] for r in stocks}
        mention_map = _build_mention_map(stocks)
    except Exception as e:
        logger.error("Failed to fetch stocks list: %s", e)
        return 0

    rows = collect_rss_news(ticker_set, mention_map)
    with pipeline_run(client, "news") as (rows_out, _):
        count = upsert_batch(client, "news", rows, on_conflict="ticker,url")
        rows_out[0] = count
    logger.info("News upserted %d rows", count)
    return count


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    logging.basicConfig(level=logging.INFO)
    run()
