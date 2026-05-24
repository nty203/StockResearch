"""평가 D — Library recall: point-in-time replay.

가장 의미 있는 평가. 라이브러리에 등록된 historical 100배 종목 각각에 대해
rise_start_date 이전 N일 시점으로 시계를 되돌려 scanner를 재실행하고,
그 시점에 우리 시스템이 해당 종목을 매칭으로 잡아냈는지 확인한다.

지표:
  - recall_at_lookback : N일 전 시점에 라이브러리 종목 중 몇 %가 매칭됐는가
  - mean_lookback_confidence : 매칭된 종목들의 평균 confidence
  - per_stock : 종목별 lookback별 hit/miss 기록

작동 원리:
  - hundredx_library_stocks 에서 rise_start_date 가 있는 종목만 선별
  - 각 종목에 대해 as_of = rise_start - lookback_days
  - scan_at(client, ticker, as_of) 실행
  - 매칭 결과가 1개 이상이면 hit, 0개면 miss
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from statistics import mean

from ..point_in_time import scan_at
from ._db import fetch_all

logger = logging.getLogger(__name__)

LOOKBACK_DAYS = [30, 90, 180, 365]
MIN_CONFIDENCE = 0.55


def _safe_date(v) -> date | None:
    if not v:
        return None
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def compute_library_recall(
    client,
    lookback_days: list[int] | None = None,
    max_stocks: int | None = None,
    exclude_categories: set[str] | None = None,
    category_thresholds: dict[str, float] | None = None,
) -> dict:
    """라이브러리 종목 point-in-time recall 측정."""
    lookback_days = lookback_days or LOOKBACK_DAYS

    lib = fetch_all(lambda s, e: (
        client.table("hundredx_library_stocks")
        .select("ticker, category, rise_start_date, peak_multiplier, earliest_signal_date")
        .order("rise_start_date", desc=True)  # 최근 종목 우선 (filings 데이터 풍부)
        .range(s, e)
    ))
    # rise_start_date 가 명시된 종목만 (point-in-time 기준점 필요)
    lib = [r for r in lib if _safe_date(r.get("rise_start_date"))]
    # 데이터 커버리지가 부족한 2020년 이전 종목 제외 (filings DB 시작점 ≈ 2020)
    lib = [r for r in lib if _safe_date(r["rise_start_date"]) >= date(2021, 1, 1)]
    if max_stocks:
        lib = lib[:max_stocks]

    # ticker 메타정보 일괄 조회
    tickers = list({r["ticker"] for r in lib})
    if not tickers:
        return {"n_library_stocks": 0, "note": "rise_start_date 가 있는 라이브러리 종목 없음"}

    meta_res = (
        client.table("stocks")
        .select("ticker, sector_tag, market_cap, market")
        .in_("ticker", tickers)
        .execute()
    )
    meta_by_ticker = {r["ticker"]: r for r in (meta_res.data or [])}

    per_stock_records = []
    hits_by_lookback: dict[int, int] = {d: 0 for d in lookback_days}
    confs_by_lookback: dict[int, list[float]] = {d: [] for d in lookback_days}
    tested_by_lookback: dict[int, int] = {d: 0 for d in lookback_days}

    for stock in lib:
        ticker = stock["ticker"]
        rise_d = _safe_date(stock.get("rise_start_date"))
        if rise_d is None:
            continue
        meta = meta_by_ticker.get(ticker, {})
        sector = meta.get("sector_tag")
        mktcap = meta.get("market_cap")

        record = {
            "ticker": ticker,
            "library_category": stock.get("category"),
            "rise_start": rise_d.isoformat(),
            "peak_multiplier": float(stock.get("peak_multiplier") or 0),
            "lookback_results": {},
        }

        for lb in lookback_days:
            as_of = rise_d - timedelta(days=lb)
            tested_by_lookback[lb] += 1
            try:
                matches = scan_at(
                    client, ticker, as_of,
                    min_confidence=MIN_CONFIDENCE,
                    sector_tag=sector,
                    market_cap=mktcap,
                    exclude_categories=exclude_categories,
                    category_thresholds=category_thresholds,
                )
            except Exception as exc:
                logger.warning("scan_at error %s @ %s: %s", ticker, as_of, exc)
                matches = []

            if matches:
                hits_by_lookback[lb] += 1
                best_conf = max(float(m.confidence) for m in matches)
                confs_by_lookback[lb].append(best_conf)
                record["lookback_results"][f"{lb}d"] = {
                    "hit": True,
                    "n_categories": len(matches),
                    "categories": sorted({m.category for m in matches}),
                    "best_confidence": round(best_conf, 3),
                }
            else:
                record["lookback_results"][f"{lb}d"] = {"hit": False}

        per_stock_records.append(record)

    by_lookback = []
    for lb in lookback_days:
        tested = tested_by_lookback[lb]
        hits = hits_by_lookback[lb]
        confs = confs_by_lookback[lb]
        by_lookback.append({
            "lookback_days": lb,
            "n_tested": tested,
            "n_hit": hits,
            "recall": round(hits / tested, 3) if tested else None,
            "mean_confidence": round(mean(confs), 3) if confs else None,
        })

    # ── Per-detector recall contribution ──────────────────────────────────────
    # 각 카테고리가 단독으로 잡은 stock 수 (unique recall) 와 함께-잡은 수 (overlap recall).
    # detector ablation을 매번 돌리지 않아도 한 번의 패스로 비교 가능.
    per_detector: dict[int, dict[str, dict[str, int]]] = {}
    for lb in lookback_days:
        det_count: dict[str, dict[str, int]] = {}
        # all_hit_categories_per_stock: 각 stock에서 fire 한 카테고리들
        for rec in per_stock_records:
            res = rec["lookback_results"].get(f"{lb}d", {})
            if not res.get("hit"):
                continue
            cats = res.get("categories") or []
            for c in cats:
                d = det_count.setdefault(c, {"fires": 0, "solo": 0, "shared": 0})
                d["fires"] += 1
                if len(cats) == 1:
                    d["solo"] += 1
                else:
                    d["shared"] += 1
        per_detector[lb] = det_count

    return {
        "n_library_stocks": len(per_stock_records),
        "lookback_days": lookback_days,
        "min_confidence": MIN_CONFIDENCE,
        "excluded_categories": sorted(exclude_categories) if exclude_categories else [],
        "category_thresholds": category_thresholds or {},
        "per_detector_by_lookback": per_detector,
        "by_lookback": by_lookback,
        "per_stock": per_stock_records,
    }
