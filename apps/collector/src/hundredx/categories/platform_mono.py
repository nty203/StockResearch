"""플랫폼_독점 detector — MONOPOLY_KEYWORDS + patent/cert keyword co-presence.

Imports from classifier.py (single source of truth).

Thresholds:
  1 monopoly keyword + 1 patent/cert keyword → confidence 0.5
  2+ monopoly keywords + 1 patent/cert keyword → confidence 0.8
"""
from __future__ import annotations
from ...triggers.classifier import MONOPOLY_KEYWORDS
from ..models import CategoryMatch

_PATENT_CERT_KEYWORDS = ["특허", "patent", "인증", "certification", "인가", "sole supplier"]


def _kw_hit(text: str, keywords: list[str]) -> list[str]:
    text_lower = text.lower()
    return [kw for kw in keywords if kw.lower() in text_lower]


def detect(stock_data: dict, filings: list[dict]) -> CategoryMatch | None:
    ticker = stock_data.get("ticker", "")
    best_confidence = 0.0
    best_evidence: list[dict] = []

    for filing in filings:
        text = (filing.get("raw_text") or "") + " " + (filing.get("headline") or "")
        if not text.strip():
            continue

        mono_hits = _kw_hit(text, MONOPOLY_KEYWORDS)
        cert_hits = _kw_hit(text, _PATENT_CERT_KEYWORDS)

        if not mono_hits or not cert_hits:
            continue

        conf = 0.8 if len(mono_hits) >= 2 else 0.5

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
                    "text_excerpt": f"독점: {', '.join(mono_hits[:3])} | 인증: {', '.join(cert_hits[:2])}",
                    "date": filing.get("filed_at"),
                    "amount": None,
                },
            ]

    if best_confidence == 0.0:
        return None

    return CategoryMatch(
        ticker=ticker,
        category="플랫폼_독점",
        confidence=best_confidence,
        evidence=best_evidence,
    )
