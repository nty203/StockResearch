"""Survivorship-free 10배+ 유니버스 구축기.

목표:
  - KOSPI/KOSDAQ에서 2000-01-01 ~ 현재, 5년 rolling window 내
    trough→peak 10배+ 달성한 모든 종목 (상장폐지/M&A 포함)
  - 같은 카테고리에서 시작했다 실패한 "loser" 케이스도 함께 수집
  - pptr_training_samples 테이블에 적재 (label = 1 if 10x+ in 24m, else 0)

FinanceDataReader는 KRX 상장폐지 종목(code 6자리)도 지원:
  fdr.DataReader('005930') — KOSPI 상장 종목
  fdr.DataReader('KRX-DELISTING') — 상장폐지 종목 목록 (name/code/date)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Iterator

logger = logging.getLogger(__name__)

WINNER_THRESHOLD_MULTIPLIER = 10.0   # 10배 이상을 winner로 정의
LOSER_HORIZON_MONTHS = 24            # 24개월 내 10배 미달이면 loser
MIN_PRICE_HISTORY_DAYS = 250         # 최소 250 거래일 이상 데이터 필요
MAX_YEARS_LOOKBACK = 20              # 2000년부터


@dataclass
class SurvivalSample:
    """ML 학습용 샘플 1개 — 특정 종목의 특정 날짜 snapshot."""
    ticker: str
    snapshot_date: str          # "YYYY-MM-DD" — 이 날짜 기준 feature 계산
    market: str                 # KOSPI / KOSDAQ
    category: str               # 라이브러리 카테고리 (없으면 '미분류')
    label_10x_24m: int          # 1 = snapshot_date 이후 24개월 내 10x 달성, 0 = 미달
    label_5x_24m: int           # 1 = 5x 달성
    label_2x_12m: int           # 1 = 12개월 내 2x 달성
    peak_multiplier: float      # snapshot 이후 최대 배율 (전체 기간)
    trough_date: str            # 실제 trough 날짜
    peak_date: str              # 실제 peak 날짜
    is_delisted: bool = False   # 상장폐지 종목 여부
    notes: str = ""


@dataclass
class UniverseStats:
    total_tickers: int = 0
    active_tickers: int = 0
    delisted_tickers: int = 0
    winners_10x: int = 0
    losers: int = 0
    samples_generated: int = 0
    errors: int = 0


def _fetch_delisted_kr() -> list[dict]:
    """KRX 상장폐지 종목 목록 조회.

    FinanceDataReader의 KRX-DELISTING 또는 KRX-KOSPI-DELISTING / KRX-KOSDAQ-DELISTING.
    반환: [{'Code': '005930', 'Name': '삼성전자', 'Market': 'KOSPI', 'DelistingDate': '2020-01-01'}, ...]
    """
    try:
        import FinanceDataReader as fdr
        import pandas as pd
        dfs = []
        for market_code, market_name in [
            ("KRX-KOSPI-DELISTING", "KOSPI"),
            ("KRX-KOSDAQ-DELISTING", "KOSDAQ"),
        ]:
            try:
                df = fdr.StockListing(market_code)
                if df is not None and not df.empty:
                    df = df.copy()
                    df["Market"] = market_name
                    dfs.append(df)
            except Exception as e:
                logger.debug("Delisted listing %s failed: %s", market_code, e)
        if not dfs:
            return []
        combined = pd.concat(dfs, ignore_index=True)
        # 컬럼 정규화
        col_map = {}
        for c in combined.columns:
            lc = c.lower()
            if lc in ("code", "symbol", "ticker"):
                col_map[c] = "Code"
            elif lc in ("name", "종목명"):
                col_map[c] = "Name"
            elif lc in ("delistingdate", "상장폐지일", "date"):
                col_map[c] = "DelistingDate"
        combined.rename(columns=col_map, inplace=True)
        return combined.to_dict("records")
    except Exception as e:
        logger.warning("Delisted fetch failed: %s", e)
        return []


def _fetch_active_kr(client) -> list[dict]:
    """Supabase stocks 테이블에서 활성 KR 종목."""
    res = (
        client.table("stocks")
        .select("ticker, market, name_kr, sector_tag")
        .eq("is_active", True)
        .in_("market", ["KOSPI", "KOSDAQ"])
        .execute()
    )
    return res.data or []


def _fetch_prices_fdr(ticker: str, start: str) -> list[tuple[str, float]]:
    """FinanceDataReader로 가격 조회 → [(date_str, close), ...]."""
    try:
        import FinanceDataReader as fdr
        df = fdr.DataReader(ticker, start)
        if df is None or df.empty:
            return []
        df = df.reset_index().sort_values("Date")
        result = []
        for _, row in df.iterrows():
            try:
                close = float(row.get("Close", 0))
                if close > 0:
                    result.append((str(row["Date"])[:10], close))
            except (TypeError, ValueError):
                continue
        return result
    except Exception as e:
        logger.debug("FDR fetch %s: %s", ticker, e)
        return []


def _compute_multipliers(
    prices: list[tuple[str, float]],
) -> list[tuple[str, float, str, float, float]]:
    """각 날짜를 trough 기준으로 삼아 이후 최대 배율 계산.

    Returns: [(trough_date, trough_price, peak_date, peak_price, multiplier), ...]
    효율적 구현: running minimum + forward pass.
    """
    if len(prices) < MIN_PRICE_HISTORY_DAYS:
        return []

    # Forward pass: 각 인덱스 i에서 i 이후 최고가 (peak)
    n = len(prices)
    # peak_ahead[i] = (peak_date, peak_price) from i to end
    peak_ahead: list[tuple[str, float]] = [("", 0.0)] * n
    best_p = 0.0
    best_d = ""
    for i in range(n - 1, -1, -1):
        d, c = prices[i]
        if c > best_p:
            best_p = c
            best_d = d
        peak_ahead[i] = (best_d, best_p)

    results = []
    for i, (d, c) in enumerate(prices):
        if c <= 0:
            continue
        peak_d, peak_p = peak_ahead[i]
        if peak_p <= 0:
            continue
        mult = peak_p / c
        results.append((d, c, peak_d, peak_p, mult))
    return results


def _label_at_date(
    prices: list[tuple[str, float]],
    snapshot_date: str,
    horizons_months: dict[str, int],  # {"label_10x_24m": 24, ...}
) -> dict[str, int]:
    """snapshot_date 이후 horizon_months 이내 배율 달성 여부 라벨 계산."""
    from datetime import datetime
    snap_dt = datetime.fromisoformat(snapshot_date).date()
    # snapshot_date에 가장 가까운 close 찾기
    snap_close = None
    for d, c in prices:
        if d >= snapshot_date:
            snap_close = c
            break
    if snap_close is None or snap_close <= 0:
        return {k: 0 for k in horizons_months}

    labels: dict[str, int] = {}
    for label, months in horizons_months.items():
        horizon_end = (snap_dt + timedelta(days=int(months * 30.5))).isoformat()
        threshold_multiplier = (
            10.0 if "10x" in label else
            5.0 if "5x" in label else
            2.0
        )
        target_price = snap_close * threshold_multiplier
        achieved = any(
            c >= target_price
            for d, c in prices
            if snapshot_date <= d <= horizon_end
        )
        labels[label] = int(achieved)
    return labels


def generate_samples_for_ticker(
    ticker: str,
    market: str,
    prices: list[tuple[str, float]],
    category: str = "미분류",
    is_delisted: bool = False,
    sample_every_n_days: int = 30,  # 월 1회 snapshot
) -> list[SurvivalSample]:
    """종목 1개의 가격 데이터에서 ML 학습 샘플 생성.

    모든 날짜를 샘플로 쓰면 너무 많고 autocorrelated → 30일 간격으로 subsample.
    """
    if not prices or len(prices) < MIN_PRICE_HISTORY_DAYS:
        return []

    multiplier_data = _compute_multipliers(prices)
    if not multiplier_data:
        return []

    # peak multiplier by trough_date
    peak_by_trough = {td: (pd_, pp, mult) for td, tp, pd_, pp, mult in multiplier_data}

    samples: list[SurvivalSample] = []
    horizon_config = {
        "label_10x_24m": 24,
        "label_5x_24m": 24,
        "label_2x_12m": 12,
    }

    for i, (d, c) in enumerate(prices):
        if i % sample_every_n_days != 0:
            continue
        # 이 날짜를 기준으로 이후 24개월이 데이터에 있어야 유의미한 라벨 계산 가능
        # (단, 상장폐지 종목은 마지막 날짜까지만 있으므로 허용)
        labels = _label_at_date(prices, d, horizon_config)

        # trough 기준 multiplier (이 날짜부터 이후 최고가 / 이 날짜 가격)
        _, _, peak_date, peak_price, peak_mult = next(
            (row for row in multiplier_data if row[0] == d), (d, c, d, c, 1.0)
        )

        samples.append(SurvivalSample(
            ticker=ticker,
            snapshot_date=d,
            market=market,
            category=category,
            label_10x_24m=labels["label_10x_24m"],
            label_5x_24m=labels["label_5x_24m"],
            label_2x_12m=labels["label_2x_12m"],
            peak_multiplier=round(peak_mult, 3),
            trough_date=d,
            peak_date=peak_date,
            is_delisted=is_delisted,
            notes="" if not is_delisted else "delisted",
        ))

    return samples


def build_survivorship_free_universe(
    client,
    years_lookback: int = MAX_YEARS_LOOKBACK,
    save_to_db: bool = True,
    max_tickers: int | None = None,
) -> UniverseStats:
    """전체 KR 유니버스 (활성 + 상장폐지) 수집 → pptr_training_samples 적재."""
    stats = UniverseStats()
    start_date = (date.today() - timedelta(days=int(years_lookback * 365.25))).isoformat()

    # 1. 활성 종목
    active_stocks = _fetch_active_kr(client)
    stats.active_tickers = len(active_stocks)
    logger.info("Active KR tickers: %d", stats.active_tickers)

    # 2. 상장폐지 종목
    delisted = _fetch_delisted_kr()
    stats.delisted_tickers = len(delisted)
    logger.info("Delisted KR tickers: %d", stats.delisted_tickers)

    # 3. 기존 라이브러리 카테고리 매핑
    lib_rows = client.table("hundredx_library_stocks").select("ticker, category").execute().data or []
    ticker_to_category: dict[str, str] = {r["ticker"]: r["category"] for r in lib_rows}

    # 4. 수집 대상 합치기
    all_tickers: list[tuple[str, str, bool]] = []  # (ticker, market, is_delisted)
    for s in active_stocks:
        all_tickers.append((s["ticker"], s["market"], False))
    for d in delisted:
        code = str(d.get("Code", "")).strip().zfill(6)
        market = d.get("Market", "KOSPI")
        if code:
            all_tickers.append((code, market, True))

    if max_tickers:
        all_tickers = all_tickers[:max_tickers]

    stats.total_tickers = len(all_tickers)
    logger.info("Total tickers to process: %d", stats.total_tickers)

    all_samples: list[SurvivalSample] = []

    for i, (ticker, market, is_delisted) in enumerate(all_tickers):
        if i % 200 == 0 and i > 0:
            logger.info("Progress: %d/%d (winners: %d, samples: %d, errors: %d)",
                        i, stats.total_tickers, stats.winners_10x,
                        len(all_samples), stats.errors)
        try:
            prices = _fetch_prices_fdr(ticker, start_date)
            if not prices:
                continue
            category = ticker_to_category.get(ticker, "미분류")
            samples = generate_samples_for_ticker(
                ticker=ticker,
                market=market,
                prices=prices,
                category=category,
                is_delisted=is_delisted,
            )
            if samples:
                winners = sum(1 for s in samples if s.label_10x_24m == 1)
                if winners > 0:
                    stats.winners_10x += 1
                else:
                    stats.losers += 1
                all_samples.extend(samples)
        except Exception as e:
            stats.errors += 1
            logger.debug("Error processing %s: %s", ticker, e)

    stats.samples_generated = len(all_samples)
    logger.info("Total samples: %d (winners_10x tickers: %d, loser tickers: %d)",
                stats.samples_generated, stats.winners_10x, stats.losers)

    if save_to_db and all_samples:
        _save_samples(client, all_samples)

    return stats


def _save_samples(client, samples: list[SurvivalSample], batch_size: int = 500) -> None:
    """pptr_training_samples 테이블에 upsert."""
    rows = [
        {
            "ticker": s.ticker,
            "snapshot_date": s.snapshot_date,
            "market": s.market,
            "category": s.category,
            "label_10x_24m": s.label_10x_24m,
            "label_5x_24m": s.label_5x_24m,
            "label_2x_12m": s.label_2x_12m,
            "peak_multiplier": s.peak_multiplier,
            "trough_date": s.trough_date,
            "peak_date": s.peak_date,
            "is_delisted": s.is_delisted,
            "notes": s.notes,
        }
        for s in samples
    ]
    saved = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i: i + batch_size]
        try:
            client.table("pptr_training_samples").upsert(
                batch, on_conflict="ticker,snapshot_date"
            ).execute()
            saved += len(batch)
        except Exception as e:
            logger.warning("Save samples batch %d error: %s", i, e)
    logger.info("Saved %d training samples", saved)


def load_training_samples(
    client,
    split: str = "train",  # "train" | "val" | "test"
) -> list[dict]:
    """Walk-forward 분할 기준으로 학습 샘플 로드.

    Train: snapshot_date < 2019-01-01
    Val:   2019-07-01 <= snapshot_date < 2023-01-01
    Test:  snapshot_date >= 2023-07-01  (절대 재튜닝 금지)
    """
    SPLITS = {
        "train": ("2000-01-01", "2018-12-31"),
        "val":   ("2019-07-01", "2022-12-31"),
        "test":  ("2023-07-01", "2099-12-31"),
    }
    start, end = SPLITS[split]
    try:
        res = (
            client.table("pptr_training_samples")
            .select("*")
            .gte("snapshot_date", start)
            .lte("snapshot_date", end)
            .execute()
        )
        return res.data or []
    except Exception as e:
        logger.warning("Load training samples failed: %s", e)
        return []


if __name__ == "__main__":
    import argparse
    import os
    logging.basicConfig(level=logging.INFO)
    from ...upsert import get_client

    parser = argparse.ArgumentParser(description="Build survivorship-free universe")
    parser.add_argument("--years", type=int, default=20)
    parser.add_argument("--max-tickers", type=int, default=None)
    parser.add_argument("--no-save", action="store_true")
    args = parser.parse_args()

    client = get_client()
    stats = build_survivorship_free_universe(
        client,
        years_lookback=args.years,
        save_to_db=not args.no_save,
        max_tickers=args.max_tickers,
    )
    print(f"\n=== Survivorship-free Universe ===")
    print(f"Total tickers: {stats.total_tickers}")
    print(f"  Active: {stats.active_tickers}, Delisted: {stats.delisted_tickers}")
    print(f"Winner tickers (10x+): {stats.winners_10x}")
    print(f"Loser tickers: {stats.losers}")
    print(f"Total samples: {stats.samples_generated}")
    print(f"Errors: {stats.errors}")
