"""수익성_급전환 detector — OPM inflection from sub-5% base.

Thresholds:
  op_margin_prev < 5% AND op_margin_ttm > op_margin_prev
  gap 2–4pp → confidence 0.6
  gap > 5pp  → confidence 0.8
"""
from __future__ import annotations
from ..models import CategoryMatch


def detect(stock_data: dict, filings: list[dict]) -> CategoryMatch | None:
    ticker = stock_data.get("ticker", "")
    op_margin_ttm = stock_data.get("op_margin_ttm")
    op_margin_prev = stock_data.get("op_margin_prev")

    if op_margin_ttm is None or op_margin_prev is None:
        return None

    # Must start from a low base
    if op_margin_prev >= 5.0:
        return None

    gap = op_margin_ttm - op_margin_prev
    if gap < 2.0:
        return None

    confidence = 0.8 if gap > 5.0 else 0.6

    evidence = [
        {
            "source_type": "financials",
            "source_id": f"{ticker}_opm",
            "text_excerpt": f"OPM {op_margin_prev:.1f}% → {op_margin_ttm:.1f}% (+{gap:.1f}pp)",
            "date": None,
            "amount": round(gap, 2),
        },
        # source_type="opm_delta" used by scanner for analog matching
        {
            "source_type": "opm_delta",
            "source_id": f"{ticker}_opm_delta",
            "text_excerpt": f"OPM delta {gap:.2f}pp",
            "date": None,
            "amount": round(gap, 2),
        },
    ]

    return CategoryMatch(
        ticker=ticker,
        category="수익성_급전환",
        confidence=confidence,
        evidence=evidence,
    )
