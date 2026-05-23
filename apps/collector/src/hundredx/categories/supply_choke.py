"""공급_병목 detector — SUPPLY_BOTTLENECK_KEYWORDS + amount threshold.

개선 사항 (2026-05-19):
  - 키워드 2개 이상 + 섹터 매칭 → conf=0.7 (금액 없어도)
  - 섹터 보너스: 조선/방산/전력기기/반도체는 +0.1
  - 금액 임계값 완화: 500억(50억 단위) → conf 0.7 (기존 1조 → 0.7)
  - 대용량 수주 (1조+) → conf=0.85 상한 없애지 않음

조 버그 수정:
  _extract_amount_krw("1조원") = 1_000 (billion 단위) 사용
  _AMOUNT_THRESHOLD_HIGH = 1_000 (1조), _AMOUNT_THRESHOLD_MID = 50 (500억)
"""
from __future__ import annotations
from ..keywords import SUPPLY_BOTTLENECK_KEYWORDS, _extract_amount_krw
from ..models import CategoryMatch

_AMOUNT_THRESHOLD_HIGH = 1_000   # 1조 KRW (billion units)
_AMOUNT_THRESHOLD_MID = 50       # 500억 KRW (billion units)

# 섹터 무관하게 공급병목을 강력히 지시하는 키워드 (conf 0.75 보장)
_HIGH_CONVICTION_SUPPLY = {
    "HBM", "HBM3E", "HBM4", "HBM3", "HBM2E", "고대역폭 메모리",
    "TC본더", "TC 본더", "CoWoS",
    "슈퍼사이클", "LNG 운반선", "LNG운반선",
    "액체냉각", "액침냉각", "immersion cooling",
    "HVDC",
}

# 공급병목 수혜 섹터
_SUPPLY_CHOKE_SECTORS = {
    "조선", "방산", "전력기기", "반도체", "장비", "소재",
    "냉각", "열관리",
    # 배터리/이차전지
    "이차전지", "2차전지", "배터리", "양극재", "음극재", "전구체",
    "battery", "cathode", "anode",
    # US sector equivalents
    "shipbuilding", "defense", "semiconductor", "power",
}


def _kw_hit(text: str, keywords: list[str]) -> list[str]:
    text_lower = text.lower()
    return [kw for kw in keywords if kw.lower() in text_lower]


def detect(stock_data: dict, filings: list[dict]) -> CategoryMatch | None:
    ticker = stock_data.get("ticker", "")
    sector_tag = (stock_data.get("sector_tag") or "").lower()
    in_target_sector = any(s in sector_tag for s in _SUPPLY_CHOKE_SECTORS)

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

        # 고신뢰도 키워드 포함 여부
        high_conv_hits = [kw for kw in hits if kw in _HIGH_CONVICTION_SUPPLY]

        # ── confidence 결정 ────────────────────────────────────────────────
        if amount is not None and amount >= _AMOUNT_THRESHOLD_HIGH:
            # 1조 이상 대형 수주 → 최고 신뢰도
            conf = 0.85
        elif high_conv_hits:
            # HBM/TC본더/슈퍼사이클 등 고신뢰도 키워드 → 섹터 무관하게 0.75
            conf = 0.75
            if amount is not None and amount >= _AMOUNT_THRESHOLD_MID:
                conf = min(0.85, conf + 0.05)  # 금액도 있으면 보너스
        elif amount is not None and amount >= _AMOUNT_THRESHOLD_MID:
            # 500억 이상 중형 수주 → 높은 신뢰도
            conf = 0.7
        elif len(hits) >= 3 and in_target_sector:
            # 금액 없어도 키워드 3개 이상 + 대상 섹터 → 0.7
            conf = 0.7
        elif len(hits) >= 2:
            # 키워드 2개 이상 → 기본 신호
            conf = 0.5
        else:
            # 키워드 1개 → 너무 약함, 섹터 매칭 시에만 채택
            conf = 0.5 if in_target_sector else 0.0

        if conf <= 0.0:
            continue

        # 섹터 보너스 (+0.1)
        if in_target_sector and conf < 0.85:
            conf = min(0.85, conf + 0.1)

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
                    "text_excerpt": f"공급 병목: {', '.join(hits[:5])} | 섹터:{sector_tag or '미분류'}",
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
