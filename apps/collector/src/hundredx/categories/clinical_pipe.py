"""임상_파이프라인 detector — BIOTECH_PIPELINE_KEYWORDS in 2 most recent filings.

Imports from classifier.py (single source of truth).

Input: filings = the 2 most recent filings for this ticker (pre-filtered by scanner
       with a 2-year window, [:2] per ticker).

Thresholds:
  keyword in 1 filing → confidence 0.5
  keyword in both recent filings → confidence 0.7

Stage-progression comparison deferred to Phase 2 (DART phase notation inconsistency).
"""
from __future__ import annotations
from ...triggers.classifier import BIOTECH_PIPELINE_KEYWORDS
from ..models import CategoryMatch


def _kw_hit(text: str, keywords: list[str]) -> list[str]:
    text_lower = text.lower()
    return [kw for kw in keywords if kw.lower() in text_lower]


def detect(stock_data: dict, filings: list[dict]) -> CategoryMatch | None:
    ticker = stock_data.get("ticker", "")

    # filings is already pre-limited to 2 most recent by scanner._fetch_filings_2y
    filings_with_hits = []
    for filing in filings[:2]:
        text = (filing.get("raw_text") or "") + " " + (filing.get("headline") or "")
        hits = _kw_hit(text, BIOTECH_PIPELINE_KEYWORDS)
        if hits:
            filings_with_hits.append((filing, hits))

    if not filings_with_hits:
        return None

    confidence = 0.7 if len(filings_with_hits) >= 2 else 0.5

    evidence = []
    for filing, hits in filings_with_hits:
        evidence.append({
            "source_type": "filing",
            "source_id": str(filing.get("id", "")),
            "text_excerpt": (filing.get("headline") or "")[:200],
            "date": filing.get("filed_at"),
            "amount": None,
        })
        evidence.append({
            "source_type": "keywords",
            "source_id": str(filing.get("id", "")) + "_kw",
            "text_excerpt": f"임상 키워드: {', '.join(hits[:4])}",
            "date": filing.get("filed_at"),
            "amount": None,
        })

    return CategoryMatch(
        ticker=ticker,
        category="임상_파이프라인",
        confidence=confidence,
        evidence=evidence,
    )
