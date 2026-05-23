"""정책_수혜 detector — GEOPOLITICAL_KEYWORDS + sector_tag validation.

개선 사항 (2026-05-19):
  - _POLICY_SECTORS 확장: 조선, 엔진, 발전기, 냉각 추가
  - 방산/조선 섹터는 conf 기본 0.7로 상향
  - 2개 이상 키워드 히트 시 +0.1 보너스
"""
from __future__ import annotations
from ..keywords import GEOPOLITICAL_KEYWORDS
from ..models import CategoryMatch

_POLICY_SECTORS = {
    "방산", "원전", "반도체", "전력기기",
    # 2026-05-19 추가
    "조선", "엔진", "발전기", "발전엔진", "냉각", "열관리",
    "소재", "배터리",
    # 2026-05-23 추가: 이차전지/EV 정책 수혜
    "이차전지", "2차전지", "양극재", "음극재", "전구체",
    "전기차", "ev", "battery",
    # US sector_tag equivalents
    "defense", "nuclear", "semiconductor", "power",
    "shipbuilding", "engine", "cooling",
}

# 정책/지정학 키워드 + 리서치 노트 특화 키워드
_EXTRA_GEO_KEYWORDS = [
    # 방산 하드웨어 수출 확대
    "방산 수출", "무기 수출", "방위산업", "K방산",
    # 원전/에너지 정책
    "원전 르네상스", "원전 수출", "SMR 개발", "에너지 안보",
    # 데이터센터 전력 정책
    "AI 전력", "데이터센터 전력", "전력망 투자", "송전망 확충",
    # 조선/엔진 정책
    "조선 수주 지원", "핵심 산업 육성",
    # 이차전지/EV 정책 (IRA, CHIPS Act, 보조금)
    "IRA", "Inflation Reduction Act", "배터리 보조금", "EV 보조금",
    "전기차 보조금", "친환경 에너지", "탄소중립 정책", "에너지 전환 정책",
    "K-배터리", "배터리 생태계", "이차전지 육성", "소재 국산화",
    "전기차 전환", "EV 전환", "내연기관 금지",
    # 조선 환경 규제 수혜
    "환경 규제", "탈탄소 선박", "IMO 규제", "친환경 선박 전환",
    "이중연료 엔진", "LNG 추진", "암모니아 추진",
]


def _kw_hit(text: str, keywords: list[str]) -> list[str]:
    text_lower = text.lower()
    return [kw for kw in keywords if kw.lower() in text_lower]


def detect(stock_data: dict, filings: list[dict]) -> CategoryMatch | None:
    ticker = stock_data.get("ticker", "")
    sector_tag = (stock_data.get("sector_tag") or "").lower()
    in_target_sector = any(s.lower() in sector_tag for s in _POLICY_SECTORS)

    best_confidence = 0.0
    best_evidence: list[dict] = []

    all_keywords = GEOPOLITICAL_KEYWORDS + _EXTRA_GEO_KEYWORDS

    for filing in filings:
        text = (filing.get("raw_text") or "") + " " + (filing.get("headline") or "")
        if not text.strip():
            continue

        hits = _kw_hit(text, all_keywords)
        if not hits:
            continue

        # 기본 confidence
        conf = 0.7 if in_target_sector else 0.5

        # 2개 이상 키워드 히트 보너스
        if len(hits) >= 2:
            conf = min(0.85, conf + 0.1)

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
                    "text_excerpt": f"정책 키워드: {', '.join(hits[:4])} | 섹터: {sector_tag or '미분류'}",
                    "date": filing.get("filed_at"),
                    "amount": None,
                },
            ]

    if best_confidence == 0.0:
        return None

    return CategoryMatch(
        ticker=ticker,
        category="정책_수혜",
        confidence=best_confidence,
        evidence=best_evidence,
    )
