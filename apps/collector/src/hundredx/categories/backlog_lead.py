"""수주잔고_선행 detector — Backlog Coverage Ratio + YoY growth.

Thresholds (from CEO plan):
  BCR = order_backlog / revenue_ttm
  BCR >= 1.5 → confidence 0.5
  BCR >= 2.0 → confidence 0.7
  backlog YoY >= 50% → +0.15 bonus
  max confidence: 1.0

보완 경로 (2026-05-19 추가):
  order_backlog이 None일 때 → 최근 90일 filings에서 수주금액 합산으로 BCR 추정
  추정 BCR은 실제 BCR보다 낮은 confidence 상한(0.6) 적용

Skips gracefully when < 2 non-null backlog quarters available.
"""
from __future__ import annotations
import re
from ..models import CategoryMatch

# 수주잔고 파싱 패턴 (filing 텍스트에서 추출)
_BACKLOG_TEXT_PATTERNS = [
    re.compile(r"수주잔[액고량]\s*[：:]\s*(\d[\d,]*(?:\.\d+)?)\s*억"),
    re.compile(r"수주잔[액고량]\s*(\d+(?:\.\d+)?)\s*조"),
    re.compile(r"총\s*수주\s*(\d[\d,]*(?:\.\d+)?)\s*억"),
    re.compile(r"계약잔액\s*[：:]\s*(\d[\d,]*(?:\.\d+)?)\s*억"),
]

_LARGE_ORDER_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*조|(\d[\d,]*(?:\.\d+)?)\s*억"
)

# 수주 관련 키워드 — 파일링에 이 단어가 있어야 수주 금액으로 인정
_ORDER_SIGNAL_KEYWORDS = [
    "수주", "공급계약", "단일판매", "계약체결", "납품계약",
    "힘센엔진", "HiMSEN", "중속엔진", "발전엔진", "데이터센터",
    "방산", "K-2", "K-9", "FA-50", "LIG", "천무",
    "HVDC", "변압기", "TC본더", "HBM",
]


def _extract_backlog_from_text(text: str) -> float | None:
    """수주잔고 명시 패턴에서 직접 추출 (억 KRW 단위)."""
    for pat in _BACKLOG_TEXT_PATTERNS:
        m = pat.search(text)
        if m:
            raw = m.group(1).replace(",", "")
            val = float(raw)
            if "조" in pat.pattern:
                val *= 10_000  # 조 → 억
            return val
    return None


def _estimate_backlog_from_orders(filings: list[dict]) -> float | None:
    """최근 90일 수주공시 금액 합산으로 수주잔고 추정 (언더추정)."""
    total = 0.0
    found = False
    for f in filings:
        text = (f.get("raw_text") or "") + " " + (f.get("headline") or "")
        # 수주 관련 공시인지 확인
        if not any(kw.lower() in text.lower() for kw in _ORDER_SIGNAL_KEYWORDS):
            continue

        # 명시적 수주잔고 있으면 우선 사용
        backlog = _extract_backlog_from_text(text)
        if backlog is not None:
            return backlog  # 직접 수주잔고 값이 있으면 합산 불필요

        # 없으면 수주 금액 파싱해서 합산 (근사)
        amount = f.get("parsed_amount")
        if amount is not None and amount > 0:
            total += amount
            found = True

    return total if found and total > 0 else None


def detect(stock_data: dict, filings: list[dict]) -> CategoryMatch | None:
    """Return a CategoryMatch if this stock shows backlog-lead pattern, else None."""
    ticker = stock_data.get("ticker", "")
    order_backlog = stock_data.get("order_backlog")
    order_backlog_prev = stock_data.get("order_backlog_prev")
    revenue_ttm = stock_data.get("revenue_ttm")

    # ── 1차: 재무데이터에 order_backlog 있는 경우 ──────────────────────────
    if order_backlog is not None and revenue_ttm and revenue_ttm > 0:
        bcr = order_backlog / revenue_ttm
        if bcr < 1.5:
            return None

        confidence = 0.5 if bcr < 2.0 else 0.7

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
                "amount": round(bcr, 3),
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
        # BCR을 analog lookup용으로도 저장
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

    # ── 2차: order_backlog 없는 경우 → filing 텍스트에서 추정 ───────────────
    if not filings:
        return None

    estimated_backlog = _estimate_backlog_from_orders(filings)
    if estimated_backlog is None or estimated_backlog <= 0:
        return None

    # revenue_ttm이 없으면 BCR 계산 불가
    if not revenue_ttm or revenue_ttm <= 0:
        # revenue 없이도 수주규모 자체가 크면 신호
        if estimated_backlog >= 500_000:  # 5조 이상 → 명백히 대형 수주잔고
            best_filing = max(filings, key=lambda f: f.get("parsed_amount") or 0, default=None)
            return CategoryMatch(
                ticker=ticker,
                category="수주잔고_선행",
                confidence=0.5,
                evidence=[{
                    "source_type": "filing_estimated",
                    "source_id": str(best_filing.get("id", "")) if best_filing else ticker,
                    "text_excerpt": f"filing 수주잔고 추정 {estimated_backlog:,.0f}억 (revenue 없음)",
                    "date": best_filing.get("filed_at") if best_filing else None,
                    "amount": estimated_backlog,
                }],
            )
        return None

    est_bcr = estimated_backlog / revenue_ttm
    if est_bcr < 1.5:
        return None

    # 추정값이므로 confidence 상한을 0.6으로 제한
    confidence = min(0.6, 0.5 if est_bcr < 2.0 else 0.6)

    best_filing = max(filings, key=lambda f: f.get("parsed_amount") or 0, default=None)
    return CategoryMatch(
        ticker=ticker,
        category="수주잔고_선행",
        confidence=confidence,
        evidence=[
            {
                "source_type": "filing_estimated",
                "source_id": str(best_filing.get("id", "")) if best_filing else ticker,
                "text_excerpt": f"filing 수주 합산 추정 BCR {est_bcr:.2f}x ({estimated_backlog:,.0f}억)",
                "date": best_filing.get("filed_at") if best_filing else None,
                "amount": round(est_bcr, 3),
            },
            {
                "source_type": "bcr",
                "source_id": f"{ticker}_bcr_estimated",
                "text_excerpt": f"BCR 추정 {est_bcr:.3f}",
                "date": None,
                "amount": round(est_bcr, 3),
            },
        ],
    )
