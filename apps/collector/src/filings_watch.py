"""Filing watcher — DART 공시 + SEC EDGAR 8-K RSS keyword filter.

개선 사항:
  - ORDER_FILING_TYPES: 수주/공급계약 공시 유형은 키워드 없어도 수집
  - KEYWORDS_KR 확장
  - _extract_amount: 조원 단위도 억 단위로 변환
  - 2026-05-23: KIND (KRX) RSS 폴백 추가 — DART_API_KEY 없을 때도 작동
"""
import logging
import re
import time
from datetime import date, timedelta

import feedparser
import edgar

from .upsert import get_client, upsert_batch, pipeline_run, retry_execute
from .utils.settings import load_settings
from .utils import telegram as tg

logger = logging.getLogger(__name__)

# ── 키워드 ─────────────────────────────────────────────────────────────────────

KEYWORDS_KR = [
    # 수주/계약
    "수주", "공급계약", "단일판매", "MOU", "업무협약",
    # CAPEX / 증설
    "증설", "신공장", "CAPEX", "착공", "생산라인",
    # 빅테크
    "빅테크", "MSFT", "Google", "Amazon", "Oracle", "AWS", "Azure", "하이퍼스케일",
    "삼성전자", "SK하이닉스", "LG전자", "현대차", "현대모비스", "NVIDIA", "Microsoft",
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
    # 바이오/임상 (임상_파이프라인 카테고리)
    "GLP-1", "GLP1", "세마글루타이드", "비만치료", "임상시험계획", "임상 1상", "임상 2상", "임상 3상",
    "기술이전", "라이선스 아웃", "마일스톤", "FDA 승인", "식약처", "품목허가",
    "바이오시밀러", "점안제", "황반변성", "ADC", "CAR-T", "CDMO",
    # 이차전지/배터리 소재 (공급_병목/정책_수혜)
    "양극재", "음극재", "전구체", "수산화리튬", "이차전지 소재", "배터리 소재",
    "전고체 배터리", "IRA", "배터리 보조금",
    # 로봇/자동화 (빅테크_파트너)
    "협동로봇", "로봇 공급", "자동화 솔루션", "유상증자 참여", "지분 취득", "콜옵션",
    # 조선 슈퍼사이클 (공급_병목)
    "슈퍼사이클", "LNG운반선", "친환경 선박", "암모니아 선박", "선가 상승", "수주잔고",
    # PCB/기판 (빅테크_파트너)
    "고다층", "MLB", "HDI", "AI 서버 기판", "데이터센터 기판",
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


def collect_kind_filings(kr_ticker_set: set[str], lookback_days: int = 1) -> list[dict]:
    """KRX KIND RSS 피드에서 공시 수집 (DART_API_KEY 불필요).

    KIND: Korea Investor Relations Network (한국거래소 기업공시채널)
    URL: https://kind.krx.co.kr — 무인증 JSON API 사용
    """
    import urllib.request
    import json

    rows = []
    try:
        today_str = date.today().strftime("%Y%m%d")
        start_str = (date.today() - timedelta(days=lookback_days)).strftime("%Y%m%d")

        # KIND 공시 목록 API (인증 불필요, CORS 없음)
        url = (
            "https://kind.krx.co.kr/disclosure/todaydisclosure.do"
            f"?method=searchTodayDisclosureSub&pageIndex=1&perPage=100"
            f"&marketType=00&searchCodeType=&corpName=&reportNm=&startDate={start_str}&endDate={today_str}"
            "&repIsuSrtCd=&orderMode=0&orderStat=D"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                text = resp.read().decode("utf-8")
                data = json.loads(text)
        except Exception:
            # 폴백: KIND HTML 파싱 불가, 빈 리스트 반환
            return []

        items = data.get("list") or []
        for item in items:
            code = str(item.get("repIsuSrtCd", "") or "").strip().zfill(6)
            if not code or code not in kr_ticker_set:
                continue

            report_nm = str(item.get("reportNm", "") or "")
            disclosed_dt = str(item.get("disclosedDt", "") or "")

            matched_kws = _match_keywords(report_nm, KEYWORDS_KR)
            is_order = _is_order_type(report_nm)

            if not matched_kws and not is_order:
                continue

            if is_order and not matched_kws:
                matched_kws = ["수주공시(KIND)"]

            # 날짜 포맷: "2026/05/23 09:01" → ISO
            filed_at = disclosed_dt[:10].replace("/", "-") + "T00:00:00+09:00" if disclosed_dt else date.today().isoformat() + "T00:00:00+09:00"

            rows.append({
                "ticker": code,
                "source": "KIND",
                "filing_type": report_nm[:50],
                "filed_at": filed_at,
                "url": f"https://kind.krx.co.kr/disclosure/todaydisclosure.do",
                "headline": report_nm,
                "raw_text": None,
                "keywords": matched_kws,
                "parsed_amount": _extract_amount(report_nm),
                "parsed_customer": None,
            })

    except Exception as e:
        logger.warning("KIND filings error: %s", e)

    logger.info("KIND filings collected: %d", len(rows))
    return rows


def collect_naver_filings(kr_ticker_set: set[str], lookback_days: int = 3) -> list[dict]:
    """NAVER Finance 모바일 API에서 공시 수집 (인증 불필요).

    엔드포인트: https://m.stock.naver.com/api/stock/{ticker}/disclosure
    종목당 최근 20개 공시 반환 (JSON).

    주의: 종목별 1회 요청 → 종목 수 많으면 rate limit 주의.
    키워드 매칭 or ORDER_FILING_TYPES 종목만 대상.
    """
    import httpx
    import random

    rows = []
    cutoff = (date.today() - timedelta(days=lookback_days)).isoformat()

    _UA = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    ]

    headers = {
        "User-Agent": random.choice(_UA),
        "Accept": "application/json",
        "Referer": "https://m.stock.naver.com/",
        "Accept-Language": "ko-KR,ko;q=0.9",
    }

    # 전 유니버스를 돌 수 없으므로 최근 활성 category_matches 종목 + 수주공시 관련 주요 종목만
    # 실용적 접근: lookback_days를 짧게 유지 + 배치 처리
    tickers_to_check = list(kr_ticker_set)[:300]  # 최대 300개 (0.3초 간격이면 90초)

    error_count = 0
    MAX_ERRORS = 10

    with httpx.Client(timeout=10, follow_redirects=True, headers=headers) as client:
        for i, ticker in enumerate(tickers_to_check):
            if error_count >= MAX_ERRORS:
                logger.warning("Too many errors in NAVER scraping, stopping early")
                break

            # Rate limiting: 랜덤 딜레이 0.2~0.5초
            if i > 0:
                time.sleep(random.uniform(0.2, 0.5))

            try:
                url = f"https://m.stock.naver.com/api/stock/{ticker}/disclosure"
                resp = client.get(url)

                if resp.status_code == 429:
                    logger.warning("NAVER rate limited, sleeping 30s")
                    time.sleep(30)
                    continue
                if resp.status_code != 200:
                    error_count += 1
                    continue

                items = resp.json()
                if not isinstance(items, list):
                    continue

                for item in items:
                    title = str(item.get("title", "") or "")
                    dt_str = str(item.get("datetime", "") or "")  # "2026-05-13T06:51:17"
                    disc_id = item.get("disclosureId", "")
                    item_code = str(item.get("itemCode", ticker))

                    # 날짜 필터
                    if dt_str and dt_str[:10] < cutoff:
                        continue

                    matched_kws = _match_keywords(title, KEYWORDS_KR)
                    is_order = _is_order_type(title)

                    if not matched_kws and not is_order:
                        continue

                    if is_order and not matched_kws:
                        matched_kws = ["수주공시(NAVER)"]

                    # filed_at
                    filed_at = (dt_str[:10] + "T" + dt_str[11:19] + "+09:00") if len(dt_str) >= 19 else (
                        date.today().isoformat() + "T00:00:00+09:00"
                    )

                    rows.append({
                        "ticker": item_code.zfill(6),
                        "source": "KIND",   # KIND로 저장 (source CHECK는 DART/SEC/KIND/SEED)
                        "filing_type": title[:50],
                        "filed_at": filed_at,
                        "url": f"https://m.stock.naver.com/domestic/stock/{ticker}/disclosure",
                        "headline": title,
                        "raw_text": None,
                        "keywords": matched_kws,
                        "parsed_amount": _extract_amount(title),
                        "parsed_customer": None,
                    })

            except httpx.TimeoutException:
                error_count += 1
                logger.debug("Timeout for ticker %s", ticker)
            except Exception as e:
                error_count += 1
                logger.debug("NAVER error for %s: %s", ticker, e)

    logger.info("NAVER filings collected: %d (checked %d tickers)", len(rows), min(len(tickers_to_check), 300))
    return rows


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

    import os
    dart_api_key = os.environ.get("DART_API_KEY", "")
    if dart_api_key:
        dart_rows = collect_dart_filings(kr_ticker_set, lookback_days)
        if not dart_rows:
            logger.info("DART returned 0 rows — supplementing with NAVER scraper")
            dart_rows += collect_naver_filings(kr_ticker_set, lookback_days)
    else:
        logger.warning("DART_API_KEY not set — using NAVER Finance as fallback scraper")
        dart_rows = collect_naver_filings(kr_ticker_set, lookback_days)
        if not dart_rows:
            logger.warning("NAVER returned 0 rows — trying KIND as last resort")
            dart_rows = collect_kind_filings(kr_ticker_set, lookback_days)

    sec_rows = collect_sec_filings(us_tickers)
    rows = dart_rows + sec_rows

    # 동일 배치 내 (ticker, filed_at, filing_type) 중복 제거 (upsert conflict 방지)
    seen: set[tuple] = set()
    deduped_rows = []
    for r in rows:
        key = (r["ticker"], r["filed_at"], r.get("filing_type", ""))
        if key not in seen:
            seen.add(key)
            deduped_rows.append(r)

    if len(deduped_rows) < len(rows):
        logger.info("Deduped %d → %d rows (removed %d duplicates)", len(rows), len(deduped_rows), len(rows) - len(deduped_rows))

    with pipeline_run(client, "filings") as (rows_out, _):
        count = upsert_batch(client, "filings", deduped_rows, on_conflict="ticker,filed_at,filing_type")
        rows_out[0] = count
    logger.info("Filings upserted %d rows (dart/kind=%d, sec=%d)", count, len(dart_rows), len(sec_rows))

    # 텔레그램 알림: 오늘 접수된 키워드 공시만 (재수집된 과거 공시 제외)
    # - lookback_days=2로 실행하면 같은 공시가 매시간 재수집될 수 있음
    # - filed_at이 오늘인 건만 알림 → 중복 발송 방지
    try:
        from datetime import datetime, timezone
        today = date.today().isoformat()  # "2026-05-23"
        fresh_filings = [
            r for r in deduped_rows
            if r.get("keywords") and str(r.get("filed_at", ""))[:10] >= today
        ]
        if fresh_filings:
            tg.notify_filing_alert(fresh_filings)
            logger.info("Telegram filing alert sent: %d fresh filings", len(fresh_filings))
    except Exception as e:
        logger.warning("Telegram filing alert failed: %s", e)

    return count


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
