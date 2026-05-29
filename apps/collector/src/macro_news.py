"""Macro news collector — 종목 태그 없이 경제/정책/산업 전반 뉴스를 누적.

news_rss.py(ticker NOT NULL, hundredx 종목별 시그널용)와 달리, 종목명이
본문에 없어도 모든 매크로 기사를 저장한다. macro-idea 스킬이 탑다운으로
투자 가설(테마)을 도출하는 입력 코퍼스로 사용한다.
"""
import logging
import time
from datetime import datetime, timezone

import feedparser

from .upsert import get_client, upsert_batch, pipeline_run
from .news_rss import _parse_date, _parse_feed_with_retry

logger = logging.getLogger(__name__)

# 종목 비특정 매크로 소스 — 경제 전반/정책/산업/시장
MACRO_FEEDS = [
    ("https://www.hankyung.com/feed/economy", "ko"),
    ("https://www.hankyung.com/feed/finance", "ko"),
    ("https://www.hankyung.com/feed/industry", "ko"),
    ("https://biz.chosun.com/rcms/rss/3/1.xml", "ko"),
    ("https://www.yna.co.kr/rss/economy.xml", "ko"),
    ("https://news.naver.com/rss/main/NEWS_OFFICIAL_GROUP_003.xml", "ko"),
    ("https://finance.yahoo.com/news/rssindex", "en"),
]

# 거친 카테고리 태깅 — macro-idea가 테마별로 필터링할 수 있도록
_CATEGORY_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("정책", ("정부", "정책", "규제", "예산", "국회", "법안", "세제", "보조금", "밸류업", "지원책")),
    ("금리환율", ("금리", "환율", "원/달러", "연준", "한은", "기준금리", "채권", "FOMC", "달러")),
    ("소비", ("소비", "내수", "유통", "백화점", "카드", "가계", "지출", "면세")),
    ("원자재", ("유가", "구리", "금속", "원자재", "곡물", "리튬", "니켈", "천연가스")),
    ("실적", ("실적", "영업이익", "어닝", "가이던스", "목표가", "컨센서스")),
    ("산업", ("반도체", "자동차", "조선", "방산", "2차전지", "배터리", "AI", "바이오", "로봇", "원전", "풍력")),
]


def _categorize(text: str) -> str:
    lowered = text.lower()
    for category, keywords in _CATEGORY_KEYWORDS:
        if any(kw.lower() in lowered for kw in keywords):
            return category
    return "기타"


def collect_macro_news() -> list[dict]:
    rows: list[dict] = []
    seen_urls: set[str] = set()
    for feed_url, lang in MACRO_FEEDS:
        try:
            feed = _parse_feed_with_retry(feed_url)
            for entry in feed.entries:
                url = entry.get("link", "")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                title = entry.get("title", "")
                summary = entry.get("summary", entry.get("description", ""))
                rows.append({
                    "source": feed.feed.get("title", feed_url)[:50],
                    "published_at": _parse_date(entry),
                    "url": url,
                    "title": title[:500],
                    "summary": summary[:1000] if summary else None,
                    "category": _categorize(f"{title} {summary}"),
                    "lang": lang,
                })
        except Exception as e:
            logger.warning("Macro RSS feed error %s: %s", feed_url, e)
        time.sleep(0.5)
    return rows


def run() -> int:
    client = get_client()
    rows = collect_macro_news()
    with pipeline_run(client, "macro_news") as (rows_out, _):
        count = upsert_batch(client, "macro_news", rows, on_conflict="url")
        rows_out[0] = count
    logger.info("Macro news upserted %d rows", count)
    return count


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
