"""빅테크_파트너 detector — BigTech equity stake + call option in same filing.

Imports keyword lists from classifier.py (single source of truth).

Thresholds:
  BigTech keyword + (콜옵션 OR 지분 취득) in same filing within 90 days
  1 hit → confidence 0.7
  BigTech + both 콜옵션 AND 지분 취득 → confidence 0.9
"""
from __future__ import annotations
from ...triggers.classifier import BIGTECH_KEYWORDS, BIGTECH_PARTNER_KEYWORDS
from ..models import CategoryMatch

_EQUITY_KEYWORDS = ["유상증자 참여", "지분 취득", "전략적 투자"]
_CALLOPT_KEYWORDS = ["콜옵션", "call option", "최대주주 전환"]


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

        bigtech_hits = _kw_hit(text, BIGTECH_KEYWORDS)
        equity_hits = _kw_hit(text, _EQUITY_KEYWORDS)
        callopt_hits = _kw_hit(text, _CALLOPT_KEYWORDS)

        if not bigtech_hits:
            continue
        if not equity_hits and not callopt_hits:
            continue

        has_equity = bool(equity_hits)
        has_callopt = bool(callopt_hits)

        if has_equity and has_callopt:
            conf = 0.9
        else:
            conf = 0.7

        if conf > best_confidence:
            best_confidence = conf
            best_evidence = [
                {
                    "source_type": "filing",
                    "source_id": str(filing.get("id", "")),
                    "text_excerpt": (filing.get("headline") or "")[:200],
                    "date": filing.get("filed_at"),
                    "amount": None,
                }
            ]
            if has_callopt:
                best_evidence.append({
                    "source_type": "filing",
                    "source_id": str(filing.get("id", "")) + "_callopt",
                    "text_excerpt": f"콜옵션 구조 탐지: {', '.join(callopt_hits[:2])}",
                    "date": filing.get("filed_at"),
                    "amount": None,
                })

    if best_confidence == 0.0:
        return None

    return CategoryMatch(
        ticker=ticker,
        category="빅테크_파트너",
        confidence=best_confidence,
        evidence=best_evidence,
    )
