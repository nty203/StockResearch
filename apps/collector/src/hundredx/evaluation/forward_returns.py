"""평가 B — Forward returns: 과거 match의 향후 수익률 측정.

scanner가 과거에 first_detected_at = T 로 만든 match에 대해,
T 이후 30d/90d/180d/365d 시점의 가격을 prices_daily에서 조회해 수익률 계산.

지표:
  - by_verdict   : confirm / uncertain / reject 그룹별 수익률 분포
  - by_category  : 카테고리별 수익률
  - by_confidence: confidence 버킷별 수익률
  - hit_2x_rate / hit_5x_rate / hit_10x_rate (지정 기간 내 N배 도달 비율)

scanner 시점-여행 없이도 작동 (이미 누적된 match 기록만 활용).
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from statistics import mean, median

from ._db import fetch_all

logger = logging.getLogger(__name__)

HORIZONS_DAYS = [30, 90, 180, 365]
HIT_THRESHOLDS = [2.0, 5.0, 10.0]


def _safe_date(v) -> date | None:
    if not v:
        return None
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def _extract_llm_verdict(evidence: list) -> str | None:
    if not evidence:
        return None
    llm = [e for e in evidence if isinstance(e, dict) and e.get("source_type") == "llm_verdict"]
    if not llm:
        return None
    last = llm[-1]
    if last.get("verdict"):
        return str(last["verdict"]).lower()
    excerpt = str(last.get("text_excerpt") or "").lower()
    for v in ("confirm", "reject", "uncertain"):
        if f"llm {v}" in excerpt or excerpt.startswith(v):
            return v
    return None


def _fetch_prices_for_match(client, ticker: str, baseline_date: date, max_horizon_days: int) -> dict[date, float]:
    """baseline ~ baseline+max_horizon 구간 일일 종가 로드."""
    end_date = baseline_date + timedelta(days=max_horizon_days + 30)
    res = (
        client.table("prices_daily")
        .select("date, close")
        .eq("ticker", ticker)
        .gte("date", baseline_date.isoformat())
        .lte("date", end_date.isoformat())
        .order("date", desc=False)
        .execute()
    )
    return {date.fromisoformat(r["date"]): float(r["close"]) for r in (res.data or []) if r.get("close")}


def _nearest_price(prices: dict[date, float], target: date, tolerance_days: int = 7) -> float | None:
    """target 이후 ±tolerance 내 가장 가까운 거래일 종가."""
    if not prices:
        return None
    if target in prices:
        return prices[target]
    sorted_dates = sorted(prices.keys())
    for d in sorted_dates:
        if d >= target:
            if (d - target).days <= tolerance_days:
                return prices[d]
            return None
    return None


def _stats(values: list[float]) -> dict:
    if not values:
        return {"n": 0}
    return {
        "n": len(values),
        "mean_pct": round(mean(values), 2),
        "median_pct": round(median(values), 2),
        "min_pct": round(min(values), 2),
        "max_pct": round(max(values), 2),
    }


def _hit_rates(returns: list[float]) -> dict:
    """N배 도달률 (returns 단위는 % return)."""
    if not returns:
        return {}
    out = {}
    for x in HIT_THRESHOLDS:
        threshold_pct = (x - 1) * 100  # 2x = +100%
        hits = sum(1 for r in returns if r >= threshold_pct)
        out[f"hit_{int(x)}x_rate"] = round(hits / len(returns), 3)
    return out


def _bucket_confidence(conf: float) -> str:
    if conf < 0.7:
        return "<0.70"
    if conf < 0.75:
        return "0.70-0.75"
    if conf < 0.80:
        return "0.75-0.80"
    if conf < 0.85:
        return "0.80-0.85"
    if conf < 0.90:
        return "0.85-0.90"
    return "0.90+"


def compute_forward_returns(
    client,
    window_days: int = 730,
    min_horizon_for_inclusion: int = 30,
) -> dict:
    """최근 window_days 내 first_detected_at 매치들의 forward returns 계산.

    min_horizon_for_inclusion: 적어도 이만큼 시간이 경과한 매치만 포함 (30d return 측정 가능).
    """
    now_d = date.today()
    earliest_cutoff = (now_d - timedelta(days=window_days)).isoformat()
    latest_cutoff = (now_d - timedelta(days=min_horizon_for_inclusion)).isoformat()

    matches = fetch_all(lambda s, e: (
        client.table("hundredx_category_matches")
        .select("ticker, category, confidence, evidence, first_detected_at")
        .gte("first_detected_at", earliest_cutoff)
        .lte("first_detected_at", latest_cutoff)
        .order("first_detected_at", desc=False)
        .range(s, e)
    ))
    logger.info("Forward-return analysis: %d matches", len(matches))

    by_verdict_returns: dict[str, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))
    by_category_returns: dict[str, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))
    by_conf_returns: dict[str, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))
    n_with_baseline = 0
    n_skipped_no_price = 0

    for m in matches:
        baseline = _safe_date(m.get("first_detected_at"))
        if not baseline:
            continue
        ticker = m["ticker"]
        prices = _fetch_prices_for_match(client, ticker, baseline, max(HORIZONS_DAYS))
        baseline_price = _nearest_price(prices, baseline, tolerance_days=10)
        if baseline_price is None or baseline_price <= 0:
            n_skipped_no_price += 1
            continue
        n_with_baseline += 1

        verdict = _extract_llm_verdict(m.get("evidence") or []) or "unverified"
        category = m["category"]
        conf_bucket = _bucket_confidence(float(m.get("confidence") or 0))

        for h in HORIZONS_DAYS:
            target = baseline + timedelta(days=h)
            if target > now_d:
                continue
            future_price = _nearest_price(prices, target, tolerance_days=10)
            if future_price is None:
                continue
            ret_pct = (future_price - baseline_price) / baseline_price * 100.0

            by_verdict_returns[verdict][h].append(ret_pct)
            by_category_returns[category][h].append(ret_pct)
            by_conf_returns[conf_bucket][h].append(ret_pct)

    def _aggregate(returns_by_h: dict[int, list[float]]) -> dict:
        out = {}
        for h in HORIZONS_DAYS:
            vals = returns_by_h.get(h, [])
            d = _stats(vals)
            d.update(_hit_rates(vals))
            out[f"{h}d"] = d
        return out

    return {
        "horizons_days": HORIZONS_DAYS,
        "n_matches_analyzed": len(matches),
        "n_with_baseline_price": n_with_baseline,
        "n_skipped_no_price": n_skipped_no_price,
        "by_verdict": {v: _aggregate(rs) for v, rs in by_verdict_returns.items()},
        "by_category": {c: _aggregate(rs) for c, rs in by_category_returns.items()},
        "by_confidence_bucket": {b: _aggregate(rs) for b, rs in by_conf_returns.items()},
    }
