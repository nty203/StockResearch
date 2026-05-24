"""수익성_급전환 detector — OPM inflection, 흑자전환, 영업레버리지 비선형 도약 포착.

개선 사항 (2026-05-19):
  - 1. 적자 탈출 (TTM 영업이익 흑자전환): op_income_prev <= 0 이고 op_income_ttm > 0 일 때 → conf = 0.85
  - 2. 영업 레버리지 (OPM 비선형 폭발): OPM gap >= 8.0pp 일 때 → conf = 0.80
  - 3. 기존 저마진 턴어라운드: prev OPM < 5% 이고 gap이 2~4pp 이면 conf = 0.60, 5~8pp 이면 conf = 0.70
"""
from __future__ import annotations
from ..models import CategoryMatch


def detect(stock_data: dict, filings: list[dict]) -> CategoryMatch | None:
    ticker = stock_data.get("ticker", "")
    
    # Quantitative financial indicators
    op_margin_ttm = stock_data.get("op_margin_ttm")
    op_margin_prev = stock_data.get("op_margin_prev")
    
    op_income_ttm = stock_data.get("op_income")
    op_income_prev = stock_data.get("op_income_prev")  # We'll use this if available in stock_data

    # We need at least basic margin info to assess inflection
    if op_margin_ttm is None or op_margin_prev is None:
        return None

    # ── FP gate 1: pre-revenue biotech 차단 ───────────────────────────
    # 영업이익률이 -50% 이하이면 매출 거의 없는 R&D 페이즈 회사 (펩트론 등).
    # 분모(매출) 변동에 OPM이 폭발적으로 변하므로 수익성_급전환 카테고리 부적합 —
    # 이런 종목은 clinical_pipe로 가야 함.
    if op_margin_prev < -50.0 or op_margin_ttm < -50.0:
        return None

    # ── FP gate 2: 매출 동반 감소 시 신뢰도 감쇠 ──────────────────────
    # OPM이 올라도 매출이 깊게 빠지면 비용절감/구조조정 결과지 성장 inflection 아님.
    rev_ttm = stock_data.get("revenue_ttm")
    rev_prev = stock_data.get("revenue_prev")
    revenue_dampener = 1.0
    if rev_ttm and rev_prev and rev_prev > 0:
        rev_yoy = (rev_ttm - rev_prev) / rev_prev * 100
        if rev_yoy < -15.0:
            revenue_dampener = 0.5   # 깊은 매출 감소 — confidence 반감
        elif rev_yoy < -5.0:
            revenue_dampener = 0.75

    gap = op_margin_ttm - op_margin_prev
    best_confidence = 0.0
    reason_text = ""

    # ── 1차: 영업이익 흑자 전환 (적자 탈출) ───────────────────────────
    # 만약 raw_income 데이터가 있고, 흑자전환이 포착되는 경우
    if op_income_ttm is not None and op_income_prev is not None:
        if op_income_prev <= 0 and op_income_ttm > 0:
            best_confidence = 0.85
            reason_text = f"영업이익 흑자전환 (적자에서 {op_income_ttm/100000000:.1f}억 흑자 도약)"

    # ── 2차: 영업 레버리지 비선형 폭발 (OPM 8%p 이상 급등) ───────────
    if gap >= 8.0:
        conf = 0.80
        if conf > best_confidence:
            best_confidence = conf
            reason_text = f"영업레버리지 폭발 (OPM {op_margin_prev:.1f}% → {op_margin_ttm:.1f}% (+{gap:.1f}pp))"

    # ── 3차: 기존 저마진 기반 점진적 체질개선 ──────────────────────────
    if op_margin_prev < 5.0 and gap >= 2.0:
        conf = 0.70 if gap >= 5.0 else 0.60
        if conf > best_confidence:
            best_confidence = conf
            reason_text = f"저마진 탈출 OPM 체질개선 (OPM {op_margin_prev:.1f}% → {op_margin_ttm:.1f}% (+{gap:.1f}pp))"

    if best_confidence == 0.0:
        return None

    best_confidence = round(best_confidence * revenue_dampener, 3)

    evidence = [
        {
            "source_type": "financials",
            "source_id": f"{ticker}_opm_inflect",
            "text_excerpt": reason_text,
            "date": None,
            "amount": round(gap, 2),
        },
        {
            "source_type": "opm_delta",
            "source_id": f"{ticker}_opm_delta",
            "text_excerpt": f"OPM delta {gap:.2f}pp | TTM OPM: {op_margin_ttm:.2f}%",
            "date": None,
            "amount": round(gap, 2),
        },
    ]

    return CategoryMatch(
        ticker=ticker,
        category="수익성_급전환",
        confidence=best_confidence,
        evidence=evidence,
    )
