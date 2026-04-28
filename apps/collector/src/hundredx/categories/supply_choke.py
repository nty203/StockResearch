"""공급_병목 detector — SUPPLY_BOTTLENECK_KEYWORDS + amount threshold.

Imports from classifier.py (single source of truth).

Thresholds (after classifier.py 조 bug fix: 1조 = 1_000 in billion units):
  keyword only → confidence 0.5
  keyword + amount >= 1_000 (1조 KRW) → confidence 0.7
"""
from __future__ import annotations
from ...triggers.classifier import SUPPLY_BOTTLENECK_KEYWORDS, _extract_amount_krw
from ..models import CategoryMatch

# After the 조 unit bug fix in classifier.py, _extract_amount_krw("1조원") == 1_000
_AMOUNT_THRESHOLD = 1_000  # 1조 KRW in billion units


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

        hits = _kw_hit(text, SUPPLY_BOTTLENECK_KEYWORDS)
        if not hits:
            continue

        amount = _extract_amount_krw(text)
        conf = 0.7 if (amount is not None and amount >= _AMOUNT_THRESHOLD) else 0.5

        if conf > best_confidence:
            best_confidence = conf
            best_evidence = [
                {
                    "source_type": "filing",
                    "source_id": str(filing.get("id", "")),
                    "text_excerpt": (filing.get("headline") or "")[:200],
                    "date": filing.get("filed_at"),
                    "amount": amount,
                },
                {
                    "source_type": "keywords",
                    "source_id": str(filing.get("id", "")) + "_kw",
                    "text_excerpt": f"공급 병목: {', '.join(hits[:3])}",
                    "date": filing.get("filed_at"),
                    "amount": None,
                },
            ]

    if best_confidence == 0.0:
        return None

    return CategoryMatch(
        ticker=ticker,
        category="공급_병목",
        confidence=best_confidence,
        evidence=best_evidence,
    )
