"""Point-in-time scanner: 특정 시점 (as_of_date) 기준으로 단일 ticker에 7개 detector 실행.

scanner.run() 의 시간-여행 버전. 핵심 사용처: library_recall 평가에서
"라이브러리 100배 종목을 rise_start - 90d 시점에 우리 시스템이 잡았을까?" 측정.

전체 universe 스캔이 아닌 단일 ticker만 실행 — recall 평가용 시간 효율적 구현.
DB write 없음, 결과만 반환.

라이브러리 self-match guard는 제거 (라이브러리 종목의 재탐지 가능성을 측정해야 하므로).
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

from ..utils.db_fetch import bulk_fetch_financials
from .models import CategoryMatch
from .categories.backlog_lead import detect as detect_backlog_lead
from .categories.profit_inflect import detect as detect_profit_inflect
from .categories.bigtech_partner import detect as detect_bigtech_partner
from .categories.platform_mono import detect as detect_platform_mono
from .categories.policy_benefit import detect as detect_policy_benefit
from .categories.supply_choke import detect as detect_supply_choke
from .categories.clinical_pipe import detect as detect_clinical_pipe

logger = logging.getLogger(__name__)

DETECTORS = [
    ("수주잔고_선행",  detect_backlog_lead),
    ("수익성_급전환",  detect_profit_inflect),
    ("빅테크_파트너",  detect_bigtech_partner),
    ("플랫폼_독점",    detect_platform_mono),
    ("정책_수혜",      detect_policy_benefit),
    ("공급_병목",      detect_supply_choke),
    ("임상_파이프라인", detect_clinical_pipe),
]


def _fetch_filings_window(
    client,
    ticker: str,
    as_of_date: date,
    days_back: int,
) -> list[dict]:
    """as_of_date 기준 과거 days_back 일 안의 filings 조회 (미래 차단)."""
    cutoff_lo = (as_of_date - timedelta(days=days_back)).isoformat()
    cutoff_hi = as_of_date.isoformat()
    res = (
        client.table("filings")
        .select("id, ticker, headline, raw_text, filed_at")
        .eq("ticker", ticker)
        .gte("filed_at", cutoff_lo)
        .lte("filed_at", cutoff_hi)
        .order("filed_at", desc=True)
        .limit(200)
        .execute()
    )
    return res.data or []


def scan_at(
    client,
    ticker: str,
    as_of_date: date,
    min_confidence: float = 0.5,
    sector_tag: str | None = None,
    market_cap: float | None = None,
    exclude_categories: set[str] | None = None,
    category_thresholds: dict[str, float] | None = None,
) -> list[CategoryMatch]:
    """as_of_date 시점에 단일 ticker에 모든 detector를 돌려 매칭 결과 반환.

    Args:
        client: Supabase client
        ticker: 평가할 종목 코드
        as_of_date: 시점 기준일 (이 날짜 이후 데이터는 사용하지 않음)
        min_confidence: 매칭으로 인정할 최소 confidence (recall 평가는 보통 0.5)
        sector_tag, market_cap: stocks 테이블 컬럼 — 호출자가 제공 (캐시 효율)

    Returns:
        confidence ≥ min_confidence 인 CategoryMatch 리스트.
    """
    # sector/market_cap 보조 fetch
    if sector_tag is None or market_cap is None:
        st_res = (
            client.table("stocks")
            .select("sector_tag, market_cap, market")
            .eq("ticker", ticker)
            .limit(1)
            .execute()
        )
        if st_res.data:
            sector_tag = sector_tag or st_res.data[0].get("sector_tag")
            market_cap = market_cap or st_res.data[0].get("market_cap")

    # Financials at as_of_date
    fin_data = bulk_fetch_financials(client, [ticker], as_of_date=as_of_date)
    stock_data = fin_data.get(ticker, {"ticker": ticker})
    stock_data["ticker"] = ticker
    stock_data["sector_tag"] = sector_tag
    stock_data["market_cap"] = market_cap

    # Filings windows: 90d for most, 2y for clinical
    filings_90d = _fetch_filings_window(client, ticker, as_of_date, days_back=90)
    filings_2y = _fetch_filings_window(client, ticker, as_of_date, days_back=730)

    matches: list[CategoryMatch] = []
    exclude = exclude_categories or set()
    thresholds = category_thresholds or {}
    for category, detector_fn in DETECTORS:
        if category in exclude:
            continue
        try:
            f = filings_2y if category == "임상_파이프라인" else filings_90d
            result = detector_fn(stock_data, f)
            if result is None:
                continue
            effective_threshold = thresholds.get(category, min_confidence)
            if result.confidence < effective_threshold:
                continue
            result.ticker = ticker
            result.category = category
            matches.append(result)
        except Exception as exc:
            logger.debug("detector %s on %s @ %s failed: %s", category, ticker, as_of_date, exc)

    return matches
