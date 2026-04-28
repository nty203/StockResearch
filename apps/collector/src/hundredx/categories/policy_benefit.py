"""정책_수혜 detector — GEOPOLITICAL_KEYWORDS + sector_tag validation.

Imports from classifier.py (single source of truth).

Thresholds:
  GEOPOLITICAL_KEYWORDS hit (base) → confidence 0.5
  + sector_tag IN ('방산', '원전', '반도체') → confidence 0.7
"""
from __future__ import annotations
from ...triggers.classifier import GEOPOLITICAL_KEYWORDS
from ..models import CategoryMatch

_POLICY_SECTORS = {"방산", "원전", "반도체", "전력기기"}


def _kw_hit(text: str, keywords: list[str]) -> list[str]:
    text_lower = text.lower()
    return [kw for kw in keywords if kw.lower() in text_lower]


def detect(stock_data: dict, filings: list[dict]) -> CategoryMatch | None:
    ticker = stock_data.get("ticker", "")
    sector_tag = stock_data.get("sector_tag") or ""
    best_confidence = 0.0
    best_evidence: list[dict] = []

    for filing in filings:
        text = (filing.get("raw_text") or "") + " " + (filing.get("headline") or "")
        if not text.strip():
            continue

        hits = _kw_hit(text, GEOPOLITICAL_KEYWORDS)
        if not hits:
            continue

        conf = 0.7 if sector_tag in _POLICY_SECTORS else 0.5

        if conf > best_confidence:
            best_confidence = conf
            best_evidence = [
                {
                    "source_type": "filing",
                    "source_id": str(filing.get("id", "")),
                    "text_excerpt": (filing.get("headline") or "")[:200],
                    "date": filing.get("filed_at"),
                    "amount": None,
                },
                {
                    "source_type": "keywords",
                    "source_id": str(filing.get("id", "")) + "_kw",
                    "text_excerpt": f"정책 키워드: {', '.join(hits[:3])} | 섹터: {sector_tag or '미분류'}",
                    "date": filing.get("filed_at"),
                    "amount": None,
                },
            ]

    if best_confidence == 0.0:
        return None

    return CategoryMatch(
        ticker=ticker,
        category="정책_수혜",
        confidence=best_confidence,
        evidence=best_evidence,
    )
