"""Self-learning confidence scoring for PPTR matches.

The detector should not treat every PPTR match as equally strong. This module
keeps the first version intentionally transparent: it combines category prior,
matched evidence, optional rule performance, and a few refutation penalties.
"""
from __future__ import annotations

from datetime import datetime, timezone
from math import exp
from typing import Any


DEFAULT_BASE_RATE = 0.34

CATEGORY_BASE_RATES = {
    "수주잔고_선행": 0.42,
    "수익성_급전환": 0.38,
    "빅테크_파트너": 0.35,
    "플랫폼_독점": 0.34,
    "공급_병목": 0.34,
    "정책_수혜": 0.31,
    "임상_파이프라인": 0.28,
}

QUANT_KEYS = {
    "bcr_at_signal",
    "backlog_yoy_pct",
    "revenue_yoy_pct",
    "revenue_growth_yoy_pct",
    "opm_delta_at_signal",
    "opm_at_signal",
}


def _safe_float(value, default: float | None = None) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, low: float = 0.05, high: float = 0.95) -> float:
    return max(low, min(high, value))


def _parse_date(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        text = str(value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        try:
            return datetime.fromisoformat(str(value).split("T")[0]).replace(tzinfo=timezone.utc)
        except ValueError:
            return None


def _condition_score(matched_conditions: list[str], conditions: dict[str, Any]) -> tuple[float, dict]:
    quant_hits = sum(1 for k in matched_conditions if k in QUANT_KEYS)
    has_keywords = "keywords" in matched_conditions
    has_amount = "amount_threshold_billions" in matched_conditions
    has_sector = "sector_required" in matched_conditions
    has_special = "special" in matched_conditions

    score = 0.0
    score += min(0.16, quant_hits * 0.055)
    score += 0.07 if has_keywords else 0.0
    score += 0.055 if has_amount else 0.0
    score += 0.035 if has_sector else 0.0
    score += 0.045 if has_special else 0.0

    min_kw = _safe_float(conditions.get("min_keyword_matches"), 0.0) or 0.0
    if has_keywords and min_kw >= 3:
        score += 0.025

    return score, {
        "quant_hits": quant_hits,
        "has_keywords": has_keywords,
        "has_amount": has_amount,
        "has_sector": has_sector,
        "has_special": has_special,
        "min_keyword_matches": min_kw,
    }


def _performance_score(performance: dict | None) -> tuple[float, dict]:
    if not isinstance(performance, dict):
        return 0.0, {"sample_size": 0, "status": "no_history"}

    sample_size = int(_safe_float(performance.get("sample_size") or performance.get("matches"), 0) or 0)
    hit_10x = _safe_float(performance.get("hit_rate_10x"), None)
    hit_30x = _safe_float(performance.get("hit_rate_30x"), None)
    false_positive = _safe_float(performance.get("false_positive_rate"), 0.0) or 0.0

    if sample_size < 5:
        return 0.0, {"sample_size": sample_size, "status": "insufficient_history"}

    hit_signal = hit_10x if hit_10x is not None else (hit_30x or 0.0) * 0.6
    reliability = 1.0 - exp(-sample_size / 20)
    score = ((hit_signal - false_positive * 0.5) - 0.08) * reliability
    score = max(-0.14, min(0.18, score))

    return score, {
        "sample_size": sample_size,
        "hit_rate_10x": hit_10x,
        "hit_rate_30x": hit_30x,
        "false_positive_rate": false_positive,
        "reliability": round(reliability, 3),
    }


def _recency_score(evidence: list[dict], now: datetime) -> tuple[float, dict]:
    dates = [_parse_date(e.get("date")) for e in evidence if isinstance(e, dict)]
    dates = [d for d in dates if d is not None]
    if not dates:
        return -0.02, {"status": "no_evidence_date"}

    latest = max(dates)
    age_days = max(0, (now - latest).days)
    if age_days <= 90:
        score = 0.06
    elif age_days <= 270:
        score = 0.03
    elif age_days <= 540:
        score = 0.0
    else:
        score = -0.08
    return score, {"latest_evidence_date": latest.date().isoformat(), "age_days": age_days}


def _refutation_penalty(stock_data: dict) -> tuple[float, dict]:
    penalties: dict[str, float] = {}

    dilution = _safe_float(
        stock_data.get("share_count_yoy_pct")
        or stock_data.get("shares_outstanding_yoy_pct")
        or stock_data.get("dilution_yoy_pct"),
        0.0,
    ) or 0.0
    if dilution >= 30:
        penalties["dilution"] = -0.10
    elif dilution >= 15:
        penalties["dilution"] = -0.05

    debt_ratio = _safe_float(stock_data.get("debt_ratio"), None)
    if debt_ratio is not None:
        if debt_ratio >= 300:
            penalties["debt_ratio"] = -0.08
        elif debt_ratio >= 200:
            penalties["debt_ratio"] = -0.04

    ev_sales = _safe_float(stock_data.get("ev_sales") or stock_data.get("ev_to_sales"), None)
    revenue_growth = _safe_float(stock_data.get("revenue_growth_yoy") or stock_data.get("revenue_yoy_pct"), None)
    if ev_sales is not None and revenue_growth is not None and revenue_growth > 0:
        growth_adjusted = ev_sales / max(1.0, revenue_growth / 20.0)
        if growth_adjusted >= 12:
            penalties["valuation"] = -0.08
        elif growth_adjusted >= 8:
            penalties["valuation"] = -0.04

    return sum(penalties.values()), penalties


def compute_pptr_confidence(
    *,
    rule: dict,
    matched_conditions: list[str],
    evidence: list[dict],
    stock_data: dict,
    now: datetime | None = None,
    filings: list[dict] | None = None,
) -> tuple[float, dict]:
    """Return (confidence, explainable breakdown) for a PPTR match.

    우선순위:
      1. LightGBM ML 모델 (pptr_model_versions.is_production=TRUE 존재 시)
      2. 기존 선형 합산 모델 (fallback)

    ML 모델이 활성화되면 breakdown에 "model": "lgbm" 표시.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    category = rule.get("category")
    conditions = rule.get("conditions") or {}

    # ── ML 모델 시도 ─────────────────────────────────────────────────────
    try:
        from .ml.confidence_model import get_model
        ml_model = get_model(auto_load=True)
        if ml_model._is_trained:
            match_meta = {
                "matched_conditions": matched_conditions,
                "keyword_hits": sum(
                    1 for e in evidence if e.get("source_type") == "keywords"
                ),
            }
            conf, feat_dict = ml_model.predict_single(
                stock_data=stock_data,
                filings=filings or [],
                match_meta=match_meta,
                category=category or "미분류",
            )
            breakdown = {
                "model": "lgbm",
                "ml_confidence": round(conf, 3),
                "top_features": {
                    k: round(v, 3)
                    for k, v in list(feat_dict.items())[:10]
                    if v != 0.0
                },
            }
            return round(conf, 3), breakdown
    except Exception:
        pass  # ML 모델 로드 실패 → 선형 fallback

    # ── 선형 fallback (기존 로직) ─────────────────────────────────────────
    base = CATEGORY_BASE_RATES.get(category, DEFAULT_BASE_RATE)
    condition_adj, condition_detail = _condition_score(matched_conditions, conditions)
    performance_adj, performance_detail = _performance_score(rule.get("performance"))
    recency_adj, recency_detail = _recency_score(evidence, now)
    refutation_adj, refutation_detail = _refutation_penalty(stock_data)

    confidence = _clamp(base + condition_adj + performance_adj + recency_adj + refutation_adj)
    breakdown = {
        "model": "linear_fallback",
        "base_rate": round(base, 3),
        "condition_score": round(condition_adj, 3),
        "performance_score": round(performance_adj, 3),
        "recency_score": round(recency_adj, 3),
        "refutation_penalty": round(refutation_adj, 3),
        "condition_detail": condition_detail,
        "performance_detail": performance_detail,
        "recency_detail": recency_detail,
        "refutation_detail": refutation_detail,
    }
    return round(confidence, 3), breakdown
