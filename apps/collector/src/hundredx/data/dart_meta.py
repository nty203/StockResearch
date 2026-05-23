"""DART 공시 메타데이터 기반 feature 추출.

DART 공시는 단순 텍스트 매칭 이상의 메타 정보를 제공:
  - report_type: 공시 종류 (단일판매공급계약/유상증자/임상시험 등)
  - filed_at: 공시일 (주가 선행 기간 측정)
  - parsed_amount: 계약금액

이를 category 분류 + feature 추출에 활용.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from .kr_nlp import classify_dart_report, detect_refutation_from_report, score_text_for_category


@dataclass
class DartMeta:
    """DART 공시 1건의 구조화된 메타데이터."""
    filing_id: str
    ticker: str
    filed_at: str                   # "YYYY-MM-DD"
    report_type: str                # 공시 종류
    headline: str
    raw_text: str
    parsed_amount: float | None     # 억 단위
    inferred_category: str          # classify_dart_report 결과
    is_refutation: bool             # 계약해지/유상증자 등
    category_scores: dict[str, float] = field(default_factory=dict)  # {cat: score}
    days_before_today: int = 0


def enrich_filing(filing: dict, as_of_date: str | None = None) -> DartMeta:
    """DB filing row → DartMeta 변환."""
    today = as_of_date or date.today().isoformat()
    filed_at = str(filing.get("filed_at", ""))[:10] or today
    try:
        days_before = (
            datetime.fromisoformat(today) - datetime.fromisoformat(filed_at)
        ).days
    except Exception:
        days_before = 0

    report_type = filing.get("report_type") or filing.get("form_type") or ""
    headline = filing.get("headline") or ""
    raw_text = filing.get("raw_text") or ""
    text_combined = f"{report_type} {headline} {raw_text}"

    inferred_cat, is_neg = classify_dart_report(report_type)
    is_refutation = is_neg or detect_refutation_from_report(report_type, text_combined)

    # 모든 카테고리 점수
    from .kr_nlp import LEXICON
    cat_scores: dict[str, float] = {}
    for cat in LEXICON:
        result = score_text_for_category(text_combined, cat, min_positive=1)
        if result["score"] > 0:
            cat_scores[cat] = result["score"]

    return DartMeta(
        filing_id=str(filing.get("id", "")),
        ticker=filing.get("ticker", ""),
        filed_at=filed_at,
        report_type=report_type,
        headline=headline[:200],
        raw_text=raw_text[:1000],
        parsed_amount=_safe_float(filing.get("parsed_amount")),
        inferred_category=inferred_cat if not inferred_cat.startswith("_") else "unknown",
        is_refutation=is_refutation,
        category_scores=cat_scores,
        days_before_today=days_before,
    )


def extract_dart_features(filings: list[dict], as_of_date: str | None = None) -> dict:
    """공시 목록 → ML feature dict.

    Returns 다음 feature들:
      dart_best_category_score: 가장 강한 카테고리 신호 점수
      dart_refutation_count: refutation 공시 수
      dart_contract_count: 계약 공시 수
      dart_max_amount_log: 최대 계약금액 log
      dart_days_since_best: 가장 강한 공시 이후 경과일
      dart_category_*: 카테고리별 누적 점수
    """
    metas = [enrich_filing(f, as_of_date) for f in filings]

    refutation_count = sum(1 for m in metas if m.is_refutation)
    contract_count = sum(1 for m in metas if "계약" in m.inferred_category or
                         m.inferred_category == "수주잔고_선행")

    # 최대 계약금액
    amounts = [m.parsed_amount for m in metas if m.parsed_amount and m.parsed_amount > 0]
    import math
    max_amount_log = math.log(max(amounts) * 100) if amounts else 0.0  # 억→원 변환

    # 카테고리별 누적 점수
    cat_scores: dict[str, float] = {}
    best_score = 0.0
    days_since_best = 999
    for m in metas:
        for cat, score in m.category_scores.items():
            cat_scores[cat] = cat_scores.get(cat, 0.0) + score
            if score > best_score:
                best_score = score
                days_since_best = m.days_before_today

    feat: dict[str, Any] = {
        "dart_best_category_score": best_score,
        "dart_refutation_count": refutation_count,
        "dart_contract_count": contract_count,
        "dart_max_amount_log": max_amount_log,
        "dart_days_since_best": days_since_best,
    }
    # 카테고리별 점수 feature
    from .kr_nlp import LEXICON
    for cat in LEXICON:
        feat[f"dart_cat_{cat}"] = cat_scores.get(cat, 0.0)

    return feat


def _safe_float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None
