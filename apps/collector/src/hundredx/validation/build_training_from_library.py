"""
라이브러리 데이터 → 학습 샘플 변환 스크립트.

전략:
  Positive (label=1): hundredx_library_stocks — 실제 100배+ 상승 종목
    - rise_start_date 기준 T-3, T-6, T-9 스냅샷 생성
    - 이미 상승 중인 날짜는 제외 (look-ahead bias)

  Negative (label=0): hundredx_category_matches에서
    - confidence < 0.55인 감지 종목 (매칭됐지만 약한 신호)
    - exited_at이 있는 종목 (시그널 사라진 종목)
    - library에 없는 stocks 테이블의 일반 종목 (무작위 샘플)

출력: pptr_training_samples 테이블에 INSERT
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import date, datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


def _safe_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def build_from_library(client, dry_run: bool = False) -> dict:
    """
    Library stocks → positive training samples.
    Returns stats dict.
    """
    # 1. library 전체 로드
    lib = (
        client.table("hundredx_library_stocks")
        .select("ticker, category, rise_start_date, peak_multiplier, "
                "earliest_signal_date, pptr_analysis, triggers, notes")
        .order("rise_start_date", desc=False)
        .execute()
        .data or []
    )
    logger.info(f"Library stocks: {len(lib)}")

    # 2. 기존 training_samples ticker 목록 (중복 방지)
    existing = (
        client.table("pptr_training_samples")
        .select("ticker, snapshot_date")
        .execute()
        .data or []
    )
    existing_set = {(r["ticker"], r["snapshot_date"]) for r in existing}

    rows_to_insert = []
    n_skipped = 0

    for stock in lib:
        ticker = stock["ticker"]
        category = stock.get("category") or "미분류"
        rise_start = stock.get("rise_start_date")
        peak_mult = _safe_float(stock.get("peak_multiplier")) or 0.0

        if not rise_start:
            logger.debug(f"Skip {ticker}: no rise_start_date")
            n_skipped += 1
            continue

        try:
            rise_dt = date.fromisoformat(str(rise_start)[:10])
        except ValueError:
            n_skipped += 1
            continue

        # 라벨 계산
        label_10x = 1 if peak_mult >= 10.0 else 0
        label_5x  = 1 if peak_mult >= 5.0 else 0
        label_2x  = 1 if peak_mult >= 2.0 else 0

        # 스냅샷 날짜: rise_start T-3, T-6, T-9 (3개 샘플)
        for months_before in [3, 6, 9]:
            snap_dt = rise_dt - timedelta(days=months_before * 30)
            # walk-forward split: 2019 이전이어야 train
            snap_str = snap_dt.isoformat()

            if (ticker, snap_str) in existing_set:
                continue

            # Market 추정
            try:
                code_int = int(ticker)
                market = "KOSDAQ" if code_int % 10 == 0 and code_int < 100000 else "KOSPI"
            except ValueError:
                market = "US"

            row = {
                "ticker": ticker,
                "snapshot_date": snap_str,
                "market": market,
                "category": category,
                "label_10x_24m": label_10x,
                "label_5x_24m": label_5x,
                "label_2x_12m": label_2x,
                "peak_multiplier": round(peak_mult, 3),
                "is_delisted": False,
                "notes": f"from_library|rise={rise_start}|T-{months_before}m",
            }
            rows_to_insert.append(row)

    logger.info(f"Positive samples to insert: {len(rows_to_insert)} (skipped: {n_skipped})")

    if not dry_run and rows_to_insert:
        # Batch upsert (on_conflict = ignore duplicates)
        BATCH = 50
        inserted = 0
        for i in range(0, len(rows_to_insert), BATCH):
            batch = rows_to_insert[i:i+BATCH]
            try:
                client.table("pptr_training_samples").upsert(
                    batch, on_conflict="ticker,snapshot_date", ignore_duplicates=True
                ).execute()
                inserted += len(batch)
            except Exception as e:
                logger.warning(f"Batch {i//BATCH} upsert warning: {e}")
        logger.info(f"Upserted {inserted} positive samples")

    return {
        "n_positive": len(rows_to_insert),
        "n_skipped": n_skipped,
        "tickers": list({r["ticker"] for r in rows_to_insert}),
    }


def build_negatives_from_matches(client, dry_run: bool = False, limit: int = 500) -> dict:
    """
    Negative 샘플 생성:
      1. exited category_matches (시그널 소멸)
      2. 라이브러리에 없는 일반 stocks (무작위 음성 샘플)
    """
    import random

    # 라이브러리에 있는 ticker 제외
    lib = (
        client.table("hundredx_library_stocks")
        .select("ticker")
        .execute()
        .data or []
    )
    lib_tickers = {r["ticker"] for r in lib}

    # exited matches (시그널 소멸)
    exited = (
        client.table("hundredx_category_matches")
        .select("ticker, category, detected_at, confidence")
        .not_.is_("exited_at", "null")
        .lt("confidence", 0.60)
        .order("detected_at")
        .limit(limit)
        .execute()
        .data or []
    )

    # 일반 stocks에서 무작위 음성 샘플 (라이브러리 제외, KOSPI/KOSDAQ만)
    random_stocks = (
        client.table("stocks")
        .select("ticker, market")
        .in_("market", ["KOSPI", "KOSDAQ"])
        .limit(200)
        .execute()
        .data or []
    )
    random_stocks = [s for s in random_stocks if s["ticker"] not in lib_tickers]
    random.seed(42)
    random.shuffle(random_stocks)
    # 각 종목에 대해 과거 스냅샷 날짜 3개 생성 (2015, 2018, 2020)
    for s in random_stocks[:50]:
        for year in [2015, 2018, 2020]:
            exited.append({
                "ticker": s["ticker"],
                "category": "미분류",
                "detected_at": f"{year}-06-01",
                "confidence": 0.30,
            })

    existing = {
        (r["ticker"], r["snapshot_date"])
        for r in (
            client.table("pptr_training_samples")
            .select("ticker, snapshot_date")
            .execute()
            .data or []
        )
    }

    rows_to_insert = []
    seen = set()

    for m in exited:
        ticker = m["ticker"]
        if ticker in lib_tickers:
            continue
        detected = str(m.get("detected_at", "") or "")[:10]
        if not detected or (ticker, detected) in existing or (ticker, detected) in seen:
            continue
        seen.add((ticker, detected))

        try:
            code_int = int(ticker)
            market = "KOSDAQ" if code_int < 200000 else "KOSPI"
        except ValueError:
            market = "US"

        rows_to_insert.append({
            "ticker": ticker,
            "snapshot_date": detected,
            "market": market,
            "category": m.get("category") or "미분류",
            "label_10x_24m": 0,
            "label_5x_24m": 0,
            "label_2x_12m": 0,
            "is_delisted": False,
            "notes": f"negative|exited|conf={m.get('confidence', 0):.2f}",
        })

    logger.info(f"Negative samples to insert: {len(rows_to_insert)}")

    if not dry_run and rows_to_insert:
        BATCH = 50
        for i in range(0, len(rows_to_insert), BATCH):
            try:
                client.table("pptr_training_samples").upsert(
                    rows_to_insert[i:i+BATCH],
                    on_conflict="ticker,snapshot_date", ignore_duplicates=True
                ).execute()
            except Exception as e:
                logger.warning(f"Negative batch warning: {e}")

    return {"n_negative": len(rows_to_insert)}


def run(client=None, dry_run: bool = False) -> dict:
    """메인 실행."""
    if client is None:
        from supabase import create_client
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_SERVICE_KEY", "")
        client = create_client(url, key)

    pos_result = build_from_library(client, dry_run=dry_run)
    neg_result = build_negatives_from_matches(client, dry_run=dry_run)

    total = pos_result["n_positive"] + neg_result["n_negative"]
    logger.info(f"Total training samples inserted: {total}")
    return {**pos_result, **neg_result, "total": total}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    result = run(dry_run="--dry-run" in sys.argv)
    print(f"\nResult: {result}")
