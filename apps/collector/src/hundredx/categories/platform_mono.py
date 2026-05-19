"""플랫폼_독점 detector — MONOPOLY_KEYWORDS + patent/cert keyword co-presence.

개선 사항 (2026-05-19):
  - _EXCLUSIVE_KEYWORDS 추가: "독점 공급", "독점 계약", "exclusive supply" 등
  - 독점 공급 계약 + 관심 섹터(반도체, 냉각, 전력기기 등) 매칭 시 특허 키워드가 없더라도 conf=0.7로 탐지
  - 기존 로직 (독점 키워드 + 특허/인증)도 병행 유지
"""
from __future__ import annotations
from ..keywords import MONOPOLY_KEYWORDS
from ..models import CategoryMatch

_PATENT_CERT_KEYWORDS = [
    "특허", "patent", "인증", "certification", "인가", "sole supplier",
    "독점 공급", "독점 계약", "단독 공급", "exclusive contract"
]

_EXCLUSIVE_KEYWORDS = [
    "독점 공급", "독점 계약", "단독 공급", "exclusive supply", "sole supplier",
    "독점공급", "독점계약", "단독공급"
]

_MONOPOLY_SECTORS = {
    "반도체", "전력기기", "냉각", "열관리", "조선", "엔진",
    "semiconductor", "power", "cooling", "engine", "defense", "방산"
}


def _kw_hit(text: str, keywords: list[str]) -> list[str]:
    text_lower = text.lower()
    return [kw for kw in keywords if kw.lower() in text_lower]


def detect(stock_data: dict, filings: list[dict]) -> CategoryMatch | None:
    ticker = stock_data.get("ticker", "")
    sector_tag = (stock_data.get("sector_tag") or "").lower()
    in_target_sector = any(s in sector_tag for s in _MONOPOLY_SECTORS)

    best_confidence = 0.0
    best_evidence: list[dict] = []

    for filing in filings:
        text = (filing.get("raw_text") or "") + " " + (filing.get("headline") or "")
        if not text.strip():
            continue

        mono_hits = _kw_hit(text, MONOPOLY_KEYWORDS)
        cert_hits = _kw_hit(text, _PATENT_CERT_KEYWORDS)
        exclusive_hits = _kw_hit(text, _EXCLUSIVE_KEYWORDS)

        # ── 1차: 명시적 독점 계약 + 대상 섹터 (특허 키워드 없어도 인정) ─────
        if exclusive_hits and in_target_sector:
            conf = 0.7
        # ── 2차: 기존 독점 키워드 + 특허/인증 공존 ──────────────────────────
        elif mono_hits and cert_hits:
            conf = 0.8 if len(mono_hits) >= 2 else 0.5
        else:
            continue

        # 섹터 보너스 (+0.1)
        if in_target_sector and conf < 0.8:
            conf = min(0.8, conf + 0.1)

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
                    "text_excerpt": (
                        f"독점/특허: {', '.join(mono_hits[:3])} | "
                        f"인증: {', '.join(cert_hits[:2])} | "
                        f"섹터: {sector_tag or '미분류'}"
                    ),
                    "date": filing.get("filed_at"),
                    "amount": None,
                },
            ]

    if best_confidence == 0.0:
        return None

    return CategoryMatch(
        ticker=ticker,
        category="플랫폼_독점",
        confidence=best_confidence,
        evidence=best_evidence,
    )
