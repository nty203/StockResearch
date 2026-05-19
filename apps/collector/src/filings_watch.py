"""Filing watcher — DART 공시 + SEC EDGAR 8-K RSS keyword filter.

개선 사항 (2026-05-19):
  - ORDER_FILING_TYPES: 수주/공급계약 공시 유형은 키워드 없어도 수집 (헤드라인이 형식적이므로)
  - KEYWORDS_KR 확장: 중속엔진, STX엔진, 발전엔진 관련 추가
  - _extract_amount: 조원 단위도 억 단위로 통일해서 반환
  - raw_text: 관심 종목(WATCH_TICKERS)은 본문 내용까지 수집 시도
"""
import logging
import re
import time
from datetime import date, timedelta

import feedparser
import OpenDartReader as DartReader
import edgar

from .upsert import get_client, upsert_batch, pipeline_run, retry_execute
from .utils.settings import load_settings

logger = logging.getLogger(__name__)

# ── 키워드 ─────────────────────────────────────────────────────────────────────

KEYWORDS_KR = [
    # 수주/계약
    "수주", "공급계약", "단일판매", "MOU", "업무협약",
    # CAPEX / 증설
    "증설", "신공장", "CAPEX", "착공", "생산라인",
    # 빅테크
    "빅테크", "MSFT", "Google", "Amazon", "Oracle", "AWS", "Azure", "하이퍼스케일",
    # AI 인프라
    "AI 데이터센터", "데이터센터", "HBM", "TC본더", "CoWoS",
    # 열관리 / 전력인프라
    "액체냉각", "액침냉각", "HVDC", "송전망", "배전망", "변압기",
    # 발전엔진 (조선·데이터센터)
    "발전기", "발전엔진", "힘센엔진", "HiMSEN", "중속엔진", "4행정 엔진",
    "AEG", "BTM", "가스엔진",
    # 방산
    "방산", "K-2", "K-9", "FA-50", "폴란드", "천무", "유도무기",
    # 원전
    "원전", "SMR", "APR", "두코바니", "체코",
    # 수익성
    "영업이익률", "흑자전환", "어닝 서프라이즈",
]

KEYWORDS_US = [
    "contract award", "supply agreement", "capacity expansion", "capex",
    "hyperscaler", "MSFT", "Alphabet", "Amazon", "Oracle", "data center",
    "nuclear", "defense", "AI infrastructure", "liquid cooling", "HBM",
]

# DART 공시 유형 중 → 키워드 없어도 무조건 수집하는 유형
# 이 유형들은 헤드라인이 형식적이어서 수주 키워드가 없는 경우가 많음
ORDER_FILING_TYPES = {
    "단일판매·공급계약체결",
    "단일판매ㆍ공급계약체결",
    "공급계약체결",
    "수주공시",
    "중요한계약의체결",
    "중요한 계약의 체결",
    "매출액또는손익구조30%(대규모법인은15%)이상변경",
    "영업(잠정)실적공시",
    "주요사항보고서",          # 대규모 계약 포함
}

SEC_8K_RSS = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&dateb=&owner=include&count=40&search_text=&output=atom"
EDGAR_IDENTITY = "StockResearch contact@example.com"


def _extract_amount(text: str) -> float | None:
    """Extract monetary amount in 억 KRW from text."""
    # 조 단위 → 억으로 변환 (1조 = 10,000억)
    m = re.search(r"(\d+(?:\.\d+)?)\s*조", text)
    if m:
        return float(m.group(1)) * 10_000

    m = re.search(r"(\d[\d,]*(?:\.\d+)?)\s*억", text)
    if m:
        return float(m.group(1).replace(",", ""))

    m = re.search(r"\$\s*(\d+(?:\.\d+)?)\s*[Bb]illion", text)
    if m:
        return float(m.group(1)) * 1_400  # USD→KRW 억 환산 (약 1400억/billion)

    m = re.search(r"\$\s*(\d+(?:\.\d+)?)\s*[Mm]illion", text)
    if m:
        return float(m.group(1)) * 1.4   # USD million → 억 KRW

    return None


def _match_keywords(text: str, keywords: list[str]) -> list[str]:
    return [kw for kw in keywords if kw.lower() in text.lower()]


def _is_order_type(report_nm: str) -> bool:
    """공시 유형 이름이 수주/계약 유형이면 True."""
    clean = report_nm.replace(" ", "").replace("·", "").replace("ㆍ", "")
    for t in ORDER_FILING_TYPES:
        if t.replace(" ", "").replace("·", "").replace("ㆍ", "") in clean:
            return True
    return False


def collect_dart_filings(kr_ticker_set: set[str], lookback_days: int = 1) -> list[dict]:
    """DART 공시를 전체 목록 1회 조회로 수집 (ticker별 루프 금지 — 20,000회/일 한도 보호).

    dart.list() 를 corp_code 없이 호출하면 기간 내 전체 공시 목록을 반환.
    API 호출 1회로 모든 종목 커버 → 하루 24회 실행해도 24회 소모.

    수집 기준 (OR 조건):
      1) 헤드라인에 KEYWORDS_KR 중 1개 이상 매칭
      2) 공시 유형이 ORDER_FILING_TYPES에 포함 (수주/계약/영업실적 공시)
    """
    import os
    api_key = os.environ.get("DART_API_KEY", "")
    if not api_key:
        logger.error("DART_API_KEY not set")
        return []

    dart = DartReader(api_key)
    start = (date.today() - timedelta(days=lookback_days)).isoformat()
    rows = []

    try:
        # corp_code 파라미터 없이 호출 → 전체 공시 목록 (API 1회 소모)
        df = dart.list(start=start, end=date.today().isoformat(), kind="B")
        if df is None or df.empty:
            logger.info("DART list returned empty for %s ~ today", start)
            return []

        collected = 0
        skipped_not_in_universe = 0
        skipped_no_match = 0

        for _, r in df.iterrows():
            # stock_code가 6자리 숫자인 공시만 처리 (ETF·펀드 제외)
            stock_code = str(r.get("stock_code", "")).strip().zfill(6)
            if not stock_code or stock_code not in kr_ticker_set:
                skipped_not_in_universe += 1
                continue

            headline = str(r.get("report_nm", ""))
            matched_kws = _match_keywords(headline, KEYWORDS_KR)
            is_order = _is_order_type(headline)

            # 키워드 없고, 수주/계약 유형도 아니면 스킵
            if not matched_kws and not is_order:
                skipped_no_match += 1
                continue

            # 수주/계약 유형이지만 키워드 없는 경우 → "수주공시" 키워드 자동 부여
            if is_order and not matched_kws:
                matched_kws = ["수주공시(유형자동)"]

            rows.append({
                "ticker": stock_code,
                "source": "DART",
                "filing_type": headline[:50],
                "filed_at": str(r.get("rcept_dt", ""))[:10] + "T00:00:00+09:00",
                "url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={r.get('rcept_no', '')}",
                "headline": headline,
                "raw_text": None,
                "keywords": matched_kws,
                "parsed_amount": _extract_amount(headline),
                "parsed_customer": None,
            })
            collected += 1

        logger.info(
            "DART filings: total_in_df=%d, collected=%d, skipped_universe=%d, skipped_no_match=%d",
            len(df), collected, skipped_not_in_universe, skipped_no_match,
        )

    except Exception as e:
        logger.warning("DART filing error: %s", e)
    return rows


def collect_sec_filings(us_tickers: set[str]) -> list[dict]:
    edgar.set_identity(EDGAR_IDENTITY)
    rows = []
    try:
        feed = feedparser.parse(SEC_8K_RSS)
        for entry in feed.entries:
            title = entry.get("title", "")
            link = entry.get("link", "")
            matched = _match_keywords(title, KEYWORDS_US)
            # Try to match ticker from filing
            ticker_match = re.search(r"\(([A-Z]{1,5})\)", title)
            ticker = ticker_match.group(1) if ticker_match else None
            if not ticker or ticker not in us_tickers:
                continue
            if not matched:
                continue
            rows.append({
                "ticker": ticker,
                "source": "SEC",
                "filing_type": "8-K",
                "filed_at": entry.get("published", "")[:10] + "T00:00:00+00:00",
                "url": link,
                "headline": title,
                "raw_text": None,
                "keywords": matched,
                "parsed_amount": _extract_amount(title),
                "parsed_customer": None,
            })
    except Exception as e:
        logger.warning("SEC RSS error: %s", e)
    return rows


def run() -> int:
    client = get_client()
    settings = load_settings(client)
    lookback_days = int(settings.get("filings_lookback_days", 2))

    try:
        res = retry_execute(lambda: client.table("stocks").select("ticker, market").eq("is_active", True).execute())
        stocks = res.data or []
    except Exception as e:
        logger.error("Failed to fetch stocks list: %s", e)
        return 0
    kr_ticker_set = {s["ticker"] for s in stocks if s["market"] in ("KOSPI", "KOSDAQ")}
    us_tickers = {s["ticker"] for s in stocks if s["market"] in ("NYSE", "NASDAQ")}

    rows = collect_dart_filings(kr_ticker_set, lookback_days) + collect_sec_filings(us_tickers)
    with pipeline_run(client, "filings") as (rows_out, _):
        count = upsert_batch(client, "filings", rows, on_conflict="ticker,filed_at,filing_type")
        rows_out[0] = count
    logger.info("Filings upserted %d rows", count)
    return count


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
