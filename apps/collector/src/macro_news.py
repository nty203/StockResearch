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
# 설계 원칙: 범용 와이어(연합뉴스 재배포) 채널은 1개로 제한,
#            나머지는 전문 미디어(더일렉, AI타임스 등)로 채워 콘텐츠 다양성 확보.
MACRO_FEEDS = [
    # ── 범용 와이어 / 경제 일간지 (각 1채널, 중복 최소화) ──
    ("https://www.yna.co.kr/rss/economy.xml", "ko"),   # 연합뉴스 경제 (와이어 대표 1채널)
    ("https://www.yna.co.kr/rss/industry.xml", "ko"),  # 연합뉴스 산업 — 유통·소비재·K뷰티 해외진출
    ("https://www.hankyung.com/feed/finance", "ko"),   # 한경 증권 (종목·시황 특화)
    ("https://www.mk.co.kr/rss/40300001/", "ko"),      # 매경 (한경과 다른 논조)
    ("https://newsis.com/RSS/economy.xml", "ko"),      # 뉴시스 경제 — 유통·소비·기업 뉴스
    # ── 전문 미디어 (범용지가 다루지 않는 심층 분석) ──
    ("https://www.thelec.kr/rss/allArticle.xml", "ko"),        # 더일렉 — 반도체/배터리/디스플레이 전문
    ("https://rss.etnews.com/Section901.xml", "ko"),           # 전자신문 — IT·AI 제조
    ("https://www.aitimes.kr/rss/allArticle.xml", "ko"),        # AI타임스 한국어 — AI·로봇·피지컬AI 전문
    # ── 글로벌 (한국 미디어가 놓치는 글로벌 공급망·매크로) ──
    ("https://finance.yahoo.com/news/rssindex", "en"),         # Yahoo Finance
    ("https://feeds.bloomberg.com/markets/news.rss", "en"),    # Bloomberg Markets
    ("https://www.kedglobal.com/rss/rssNews", "en"),           # KED Global (영문 한국경제)
    ("https://wwd.com/beauty-industry-news/feed/", "en"),      # WWD Beauty — 글로벌 뷰티·K뷰티 리테일
    ("https://wwd.com/business-news/feed/", "en"),             # WWD Business — 글로벌 패션·리테일 전략
]

# 거친 카테고리 태깅 — macro-idea가 테마별로 필터링할 수 있도록.
# '빅테크발언'을 맨 앞에 둬 거물 발언이 산업/기타로 묻히지 않게 한다.
# (글로벌 빅테크 CEO 발언은 AI 밸류체인 주가의 선행 신호가 되는 경우가 많음)
_CATEGORY_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("빅테크발언", (
        "젠슨 황", "젠슨황", "황 ceo", "jensen", "엔비디아 ceo", "엔비디아 황",
        "순다르 피차이", "피차이", "사티아 나델라", "나델라",
        "샘 올트먼", "샘 알트먼", "올트먼", "알트먼", "altman",
        "일론 머스크", "머스크", "musk", "리사 수", "lisa su",
        "저커버그", "주커버그", "zuckerberg",
    )),
    ("정책", ("정부", "정책", "규제", "예산", "국회", "법안", "세제", "보조금", "밸류업", "지원책",
             "IRA", "인플레이션감축법", "방위비", "방산수출", "NATO", "방위산업", "국방예산")),
    ("금리환율", ("금리", "환율", "원/달러", "연준", "한은", "기준금리", "채권", "FOMC", "달러",
               "인플레이션", "물가", "CPI", "긴축", "피벗")),
    ("소비", ("소비", "내수", "유통", "백화점", "카드", "가계", "지출", "면세",
             "명품", "관광", "외국인 관광", "한류", "뷰티", "화장품", "외식", "방한",
             "ODM", "K뷰티", "K-뷰티", "이커머스", "직구")),
    ("원자재", ("유가", "구리", "금속", "원자재", "곡물", "리튬", "니켈", "천연가스",
              "LNG", "석유", "정유", "유황", "알루미늄", "철광석")),
    ("실적", ("실적", "영업이익", "어닝", "가이던스", "목표가", "컨센서스",
             "역대", "사상 최대", "호실적", "깜짝 실적", "수주", "수주잔고", "흑자전환")),
    ("산업", ("반도체", "자동차", "조선", "방산", "2차전지", "배터리", "AI", "바이오", "로봇", "원전", "풍력",
             "변압기", "전기기기", "차단기", "케이블", "배전", "송전", "전력망", "그리드",
             "ESS", "에너지저장", "MLCC", "PCB", "기판", "HBM", "메모리", "파운드리",
             "방위", "무기", "항공우주", "위성", "드론", "K방산")),
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
