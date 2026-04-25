"""Filing watcher — DART 공시 + SEC EDGAR 8-K RSS keyword filter."""
import logging
import re
import time
from datetime import date, timedelta

import feedparser
from OpenDartReader import OpenDartReader as DartReader
import edgar

from .upsert import get_client, upsert_batch
from .screening.settings_loader import load_settings

logger = logging.getLogger(__name__)

# Keywords from report 5-E recipe
KEYWORDS_KR = [
    "수주", "공급계약", "MOU", "업무협약", "증설", "신공장", "CAPEX",
    "빅테크", "MSFT", "Google", "Amazon", "Oracle", "AWS", "Azure",
    "방산", "원전", "AI 데이터센터", "HBM", "TC본더", "CoWoS",
]
KEYWORDS_US = [
    "contract award", "supply agreement", "capacity expansion", "capex",
    "hyperscaler", "MSFT", "Alphabet", "Amazon", "Oracle", "data center",
    "nuclear", "defense", "AI infrastructure",
]

SEC_8K_RSS = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&dateb=&owner=include&count=40&search_text=&output=atom"
EDGAR_IDENTITY = "StockResearch contact@example.com"


def _extract_amount(text: str) -> float | None:
    """Extract monetary amount from text (billions/trillions)."""
    patterns = [
        r"(\d+(?:\.\d+)?)\s*조",
        r"(\d+(?:\.\d+)?)\s*억",
        r"\$(\d+(?:\.\d+)?)\s*[Bb]illion",
        r"\$(\d+(?:\.\d+)?)\s*[Mm]illion",
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            return float(m.group(1))
    return None


def _match_keywords(text: str, keywords: list[str]) -> list[str]:
    return [kw for kw in keywords if kw.lower() in text.lower()]


def collect_dart_filings(tickers: list[str], lookback_days: int = 1) -> list[dict]:
    import os
    api_key = os.environ.get("DART_API_KEY", "")
    if not api_key:
        logger.error("DART_API_KEY not set")
        return []

    dart = DartReader(api_key)
    start = (date.today() - timedelta(days=lookback_days)).isoformat()
    rows = []

    for ticker in tickers:
        try:
            df = dart.list(ticker, start=start, end=date.today().isoformat(), kind="B")
            if df is None or df.empty:
                continue
            for _, r in df.iterrows():
                headline = str(r.get("report_nm", ""))
                matched = _match_keywords(headline, KEYWORDS_KR)
                if not matched:
                    continue
                rows.append({
                    "ticker": ticker,
                    "source": "DART",
                    "filing_type": str(r.get("report_nm", ""))[:50],
                    "filed_at": str(r.get("rcept_dt", ""))[:10] + "T00:00:00+09:00",
                    "url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={r.get('rcept_no', '')}",
                    "headline": headline,
                    "raw_text": None,
                    "keywords": matched,
                    "parsed_amount": _extract_amount(headline),
                    "parsed_customer": None,
                })
            time.sleep(0.05)
        except Exception as e:
            logger.warning("DART filing error %s: %s", ticker, e)
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

    res = client.table("stocks").select("ticker, market").eq("is_active", True).execute()
    stocks = res.data or []
    kr_tickers = [s["ticker"] for s in stocks if s["market"] in ("KOSPI", "KOSDAQ")]
    us_tickers = {s["ticker"] for s in stocks if s["market"] in ("NYSE", "NASDAQ")}

    rows = collect_dart_filings(kr_tickers, lookback_days) + collect_sec_filings(us_tickers)
    count = upsert_batch(client, "filings", rows, on_conflict="ticker,filed_at,filing_type")
    logger.info("Filings upserted %d rows", count)
    return count


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
