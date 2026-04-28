"""수주잔고_선행 detector — Backlog Coverage Ratio + YoY growth.

Thresholds (from CEO plan):
  BCR = order_backlog / revenue_ttm
  BCR >= 1.5 → confidence 0.5
  BCR >= 2.0 → confidence 0.7
  backlog YoY >= 50% → +0.15 bonus
  max confidence: 1.0

Skips gracefully when < 2 non-null backlog quarters available.
"""
from __future__ import annotations
from ..models import CategoryMatch


def detect(stock_data: dict, filings: list[dict]) -> CategoryMatch | None:
    """Return a CategoryMatch if this stock shows backlog-lead pattern, else None."""
    ticker = stock_data.get("ticker", "")
    order_backlog = stock_data.get("order_backlog")
    order_backlog_prev = stock_data.get("order_backlog_prev")
    revenue_ttm = stock_data.get("revenue_ttm")

    # Need at least current backlog and revenue TTM
    if order_backlog is None or not revenue_ttm or revenue_ttm <= 0:
        return None

    # BCR (Backlog Coverage Ratio)
    bcr = order_backlog / revenue_ttm

    if bcr < 1.5:
        return None

    confidence = 0.5 if bcr < 2.0 else 0.7

    # YoY growth bonus
    backlog_yoy_pct: float | None = None
    if order_backlog_prev is not None and order_backlog_prev > 0:
        backlog_yoy_pct = (order_backlog - order_backlog_prev) / order_backlog_prev * 100
        if backlog_yoy_pct >= 50:
            confidence = min(1.0, confidence + 0.15)

    evidence = [
        {
            "source_type": "financials",
            "source_id": f"{ticker}_backlog",
            "text_excerpt": f"BCR {bcr:.2f}x, order_backlog {order_backlog:,.0f}",
            "date": None,
            "amount": round(bcr, 3),  # bcr value for analog matching
        }
    ]
    if backlog_yoy_pct is not None:
        evidence.append({
            "source_type": "financials",
            "source_id": f"{ticker}_backlog_yoy",
            "text_excerpt": f"수주잔고 YoY {backlog_yoy_pct:+.1f}%",
            "date": None,
            "amount": round(backlog_yoy_pct, 1),
        })

    # Store BCR in evidence with source_type="bcr" for analog lookup in scanner
    evidence.append({
        "source_type": "bcr",
        "source_id": f"{ticker}_bcr",
        "text_excerpt": f"BCR {bcr:.3f}",
        "date": None,
        "amount": round(bcr, 3),
    })

    return CategoryMatch(
        ticker=ticker,
        category="수주잔고_선행",
        confidence=confidence,
        evidence=evidence,
    )
