"""임상_파이프라인 detector — 키워드 존재 + 단계 전이 감지.

Stage-progression comparison (Phase 2 upgrade):
  가장 최근 공시 vs. 그 이전 공시의 임상 단계를 비교.
  단계가 상승하면(1상→2상, 2상→3상, IND→1상, 3상→승인 등) confidence 보정.

Confidence table:
  keyword hit 없음         → None (no match)
  keyword 1개 공시에만     → 0.5
  keyword 2개 공시 모두    → 0.7
  keyword + 단계 전이 감지  → 0.85
  keyword + 2단계+ 전이    → 0.9
"""
from __future__ import annotations
import re
from ..keywords import BIOTECH_PIPELINE_KEYWORDS
from ..models import CategoryMatch

# Stage hierarchy: higher number = later / more advanced
_STAGE_PATTERNS: list[tuple[int, list[str]]] = [
    (0, ["IND", "임상시험계획승인", "임상시험계획"]),
    (1, ["1상", "phase 1", "phase i", "1/2상", "임상 1상"]),
    (2, ["2상", "phase 2", "phase ii", "2/3상", "임상 2상"]),
    (3, ["3상", "phase 3", "phase iii", "임상 3상"]),
    (4, ["nda", "bla", "품목허가", "허가 신청", "fda 신청"]),
    (5, ["fda 승인", "fda approval", "식약처 승인", "품목허가 획득", "최종 허가"]),
]


def _kw_hit(text: str, keywords: list[str]) -> list[str]:
    text_lower = text.lower()
    return [kw for kw in keywords if kw.lower() in text_lower]


def _detect_stage(text: str) -> int | None:
    """Return highest stage number found in text, or None."""
    text_lower = text.lower()
    found: list[int] = []
    for stage_num, patterns in _STAGE_PATTERNS:
        for pat in patterns:
            if pat.lower() in text_lower:
                found.append(stage_num)
                break
    return max(found) if found else None


def detect(stock_data: dict, filings: list[dict]) -> CategoryMatch | None:
    ticker = stock_data.get("ticker", "")

    # filings is already pre-limited to 2 most recent by scanner._fetch_filings_2y
    filings_with_hits: list[tuple[dict, list[str], int | None]] = []
    for filing in filings[:2]:
        text = (filing.get("raw_text") or "") + " " + (filing.get("headline") or "")
        hits = _kw_hit(text, BIOTECH_PIPELINE_KEYWORDS)
        stage = _detect_stage(text)
        if hits or stage is not None:
            filings_with_hits.append((filing, hits, stage))

    if not filings_with_hits:
        return None

    # Base confidence from keyword spread
    all_have_hits = all(hits for _, hits, _ in filings_with_hits)
    base_confidence = 0.7 if (len(filings_with_hits) >= 2 and all_have_hits) else 0.5

    # Stage-progression bonus: most recent filing advanced beyond previous
    stage_delta = 0
    if len(filings_with_hits) >= 2:
        _, _, stage_recent = filings_with_hits[0]
        _, _, stage_prev = filings_with_hits[1]
        if stage_recent is not None and stage_prev is not None and stage_recent > stage_prev:
            stage_delta = stage_recent - stage_prev

    if stage_delta >= 2:
        confidence = 0.9
    elif stage_delta == 1:
        confidence = 0.85
    else:
        confidence = base_confidence

    evidence: list[dict] = []
    for filing, hits, stage in filings_with_hits:
        evidence.append({
            "source_type": "filing",
            "source_id": str(filing.get("id", "")),
            "text_excerpt": (filing.get("headline") or "")[:200],
            "date": filing.get("filed_at"),
            "amount": None,
        })
        if hits:
            evidence.append({
                "source_type": "keywords",
                "source_id": str(filing.get("id", "")) + "_kw",
                "text_excerpt": f"임상 키워드: {', '.join(hits[:4])}",
                "date": filing.get("filed_at"),
                "amount": None,
            })

    # Stage transition evidence
    if stage_delta > 0 and len(filings_with_hits) >= 2:
        _, _, s0 = filings_with_hits[1]  # older
        _, _, s1 = filings_with_hits[0]  # recent
        _stage_names = {0: "IND", 1: "1상", 2: "2상", 3: "3상", 4: "허가 신청", 5: "최종 승인"}
        evidence.append({
            "source_type": "stage_transition",
            "source_id": "stage_delta",
            "text_excerpt": (
                f"임상 단계 전이: {_stage_names.get(s0, f'단계{s0}')} → "
                f"{_stage_names.get(s1, f'단계{s1}')} (+{stage_delta}단계)"
            ),
            "date": filings_with_hits[0][0].get("filed_at"),
            "amount": float(stage_delta),
        })

    return CategoryMatch(
        ticker=ticker,
        category="임상_파이프라인",
        confidence=confidence,
        evidence=evidence,
    )
