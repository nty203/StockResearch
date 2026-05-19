"""Backfill DART filings for key watch-list tickers.

대상: 리서치 노트 1~3순위 + HVDC/냉각 후보
  272210 한화엔진, 077970 STX엔진, 329180 HD현대중공업
  064350 현대로템, 012450 한화에어로스페이스, 267260 HD현대마린엔진
  006220 세명전기, 010130 제룡산업, 083450 GST, 053080 케이엔솔
  042700 한미반도체

실행:
  uv run python backfill_filings.py             # 기본 90일
  uv run python backfill_filings.py --days 180  # 180일
"""
import argparse
import logging
import os
from src.upsert import get_client, upsert_batch
from src.filings_watch import collect_dart_filings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 관심 종목 전체 — 수주잔고_선행, 공급_병목, 정책_수혜 탐지 대상
WATCH_TICKERS = {
    # 발전엔진 / 데이터센터 전력
    "272210",   # 한화엔진
    "077970",   # STX엔진
    "329180",   # HD현대중공업
    "267260",   # HD현대마린엔진
    # 방산
    "064350",   # 현대로템
    "012450",   # 한화에어로스페이스
    "047810",   # 한국항공우주(KAI)
    "079550",   # LIG넥스원
    # 전력기기 / HVDC
    "006220",   # 세명전기
    "010130",   # 제룡산업
    "267260",   # 효성중공업은 별도 확인 필요
    # 열관리 / 냉각
    "083450",   # GST
    "053080",   # 케이엔솔
    # 반도체 장비
    "042700",   # 한미반도체
    "103590",   # 이수페타시스
}


def backfill(days: int = 90):
    client = get_client()
    logger.info("Backfilling %d tickers for last %d days...", len(WATCH_TICKERS), days)

    rows = collect_dart_filings(WATCH_TICKERS, lookback_days=days)

    if rows:
        count = upsert_batch(client, "filings", rows, on_conflict="ticker,filed_at,filing_type")
        logger.info("Backfilled %d filings", count)
        print(f"\n✅ Backfilled {count} filings for {len(WATCH_TICKERS)} watch tickers")

        # 종목별 요약
        from collections import Counter
        by_ticker = Counter(r["ticker"] for r in rows)
        print("\nFilings per ticker:")
        for ticker, cnt in sorted(by_ticker.items(), key=lambda x: -x[1]):
            print(f"  [{ticker}] {cnt}건")
    else:
        print("\n⚠️  No filings found. Check DART_API_KEY and try again.")
        print("   Hint: DART_API_KEY may not be set in environment.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=90, help="Lookback days (default: 90)")
    args = parser.parse_args()
    backfill(args.days)
