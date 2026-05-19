"""빅테크_파트너 detector — BigTech equity stake + call option or high-profile supply contract.

개선 사항 (2026-05-19):
  - 1. 기존 지분 취득 및 콜옵션 투자 구조 (conf = 0.70 ~ 0.90) 유지
  - 2. 신규: 글로벌 빅테크/선도기업과의 대형 공급/협력 계약 포착 (conf = 0.75)
    - BIGTECH_KEYWORDS + 공급/협력 키워드 + 핵심 섹터 매칭 시 인정
"""
from __future__ import annotations
from ..keywords import BIGTECH_KEYWORDS
from ..models import CategoryMatch

_EQUITY_KEYWORDS = [
    "유상증자 참여", "지분 취득", "전략적 투자", "지분 인수", "3자배정",
    "equity investment", "strategic investment", "acquired stake",
    "stake acquisition", "strategic partnership agreement",
]
_CALLOPT_KEYWORDS = [
    "콜옵션", "call option", "최대주주 전환", "전환사채 취득",
    "warrant", "option to acquire", "right to purchase", "controlling interest",
]

_SUPPLY_KEYWORDS = [
    "공급", "계약", "납품", "협력", "파트너십", "수주", "개발",
    "supply", "contract", "partnership", "agreement", "deliver", "co-develop",
    "sole supplier", "exclusive contract"
]

_BIGTECH_SECTORS = {
    "반도체", "전력기기", "냉각", "열관리", "조선", "엔진", "방산",
    "semiconductor", "power", "cooling", "engine", "defense"
}


def _kw_hit(text: str, keywords: list[str]) -> list[str]:
    text_lower = text.lower()
    return [kw for kw in keywords if kw.lower() in text_lower]


def detect(stock_data: dict, filings: list[dict]) -> CategoryMatch | None:
    ticker = stock_data.get("ticker", "")
    sector_tag = (stock_data.get("sector_tag") or "").lower()
    in_target_sector = any(s in sector_tag for s in _BIGTECH_SECTORS)

    best_confidence = 0.0
    best_evidence: list[dict] = []

    for filing in filings:
        text = (filing.get("raw_text") or "") + " " + (filing.get("headline") or "")
        if not text.strip():
            continue

        bigtech_hits = _kw_hit(text, BIGTECH_KEYWORDS)
        if not bigtech_hits:
            continue

        equity_hits = _kw_hit(text, _EQUITY_KEYWORDS)
        callopt_hits = _kw_hit(text, _CALLOPT_KEYWORDS)
        supply_hits = _kw_hit(text, _SUPPLY_KEYWORDS)

        # ── 1차: 지분 취득 및 콜옵션 투자 구조 (M&A) ─────────────────
        if equity_hits and callopt_hits:
            conf = 0.90
        elif equity_hits or callopt_hits:
            conf = 0.70
        # ── 2차: 대형 빅테크 대상 공급/협력 계약 + 핵심 섹터 ──────────
        elif supply_hits and in_target_sector:
            conf = 0.75
        else:
            continue

        # 섹터 보너스 (+0.05)
        if in_target_sector and conf < 0.90:
            conf = min(0.90, conf + 0.05)

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
            if callopt_hits:
                best_evidence.append({
                    "source_type": "keywords",
                    "source_id": str(filing.get("id", "")) + "_callopt",
                    "text_excerpt": f"콜옵션/투자 조건: {', '.join(callopt_hits[:2])}",
                    "date": filing.get("filed_at"),
                    "amount": None,
                })
            elif supply_hits:
                best_evidence.append({
                    "source_type": "keywords",
                    "source_id": str(filing.get("id", "")) + "_supply",
                    "text_excerpt": f"공급/개발 협업: {', '.join(supply_hits[:2])} | 빅테크: {', '.join(bigtech_hits[:2])}",
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
