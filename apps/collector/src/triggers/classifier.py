"""Trigger event classifier — 15 trigger types from report section 5.

Each rule set: keyword match + optional amount/ratio threshold.
Returns TriggerResult with type, confidence, and matched evidence.
"""
from __future__ import annotations
import re
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ── Trigger type identifiers ───────────────────────────────────────────────
TRIGGER_TYPES = [
    "단일_수주",       # 1. Single large order from bigtech
    "CAPEX_증설",      # 2. Capacity expansion / new factory
    "글로벌_메가계약", # 3. Global mega contract (defense, nuclear)
    "빅테크_파트너",   # 4. Bigtech partnership announcement
    "시장_독점",       # 5. Market dominance / monopoly signal
    "기술_돌파",       # 6. Technology breakthrough / patent
    "수익성_급등",     # 7. Sudden profitability surge
    "내부자_매수",     # 8. Insider buying signal
    "기관_집중",       # 9. Institutional accumulation
    "규제_해소",       # 10. Regulatory barrier removed
    "공급_병목",       # 11. Supply bottleneck beneficiary
    "원자재_가격",     # 12. Raw material price inflection
    "지정학_수혜",     # 13. Geopolitical beneficiary
    "스핀오프",        # 14. Spinoff / restructuring unlock
    "실적_서프라이즈", # 15. Earnings surprise
]

BIGTECH_KEYWORDS = ["MSFT", "Microsoft", "Google", "Alphabet", "Amazon", "AWS",
                     "Oracle", "Meta", "NVIDIA", "Apple", "Tesla", "PPA",
                     "하이퍼스케일", "하이퍼스케일러", "빅테크", "CSP"]

CAPEX_KEYWORDS = ["증설", "신공장", "CAPEX", "설비투자", "ground breaking",
                  "groundbreaking", "착공", "공장 건설", "생산라인", "라인 증설",
                  "capacity expansion", "new facility", "manufacturing expansion"]

GLOBAL_MEGA_KEYWORDS = ["방산", "원전", "SMR", "nuclear", "defense", "NATO",
                         "방위", "국방", "수출", "해외 수주", "overseas contract",
                         "조원", "trillion won", "billion dollar"]

BIGTECH_PARTNER_KEYWORDS = ["전략적 파트너십", "strategic partnership", "MOU",
                              "공급 계약", "supply agreement", "preferred supplier",
                              "독점 공급", "exclusive supply", "벤더 선정"]

MONOPOLY_KEYWORDS = ["독점", "유일", "sole supplier", "only supplier", "시장점유율",
                      "market share", "지배적", "dominant", "1위", "No.1"]

TECH_BREAKTHROUGH_KEYWORDS = ["특허", "patent", "기술 혁신", "breakthrough",
                                "세계 최초", "world first", "업계 최초",
                                "양산 성공", "mass production", "인증 획득"]

PROFITABILITY_KEYWORDS = ["영업이익률", "operating margin", "흑자 전환", "턴어라운드",
                           "turnaround", "흑자", "profit improvement", "수익성 개선"]

INSIDER_BUY_KEYWORDS = ["자사주 매입", "buyback", "share repurchase", "내부자 매수",
                         "임원 매수", "대주주 매입", "insider purchase"]

INSTITUTIONAL_KEYWORDS = ["기관 순매수", "외국인 순매수", "institutional buying",
                           "펀드 편입", "ETF 편입", "index inclusion", "벤치마크"]

REGULATORY_KEYWORDS = ["규제 완화", "승인", "허가", "FDA approval", "CE 인증",
                        "regulatory approval", "규제 해소", "법안 통과"]

SUPPLY_BOTTLENECK_KEYWORDS = ["공급 부족", "supply shortage", "병목", "bottleneck",
                               "수급 불균형", "공급 타이트", "수요 초과", "sold out"]

RAW_MATERIAL_KEYWORDS = ["원자재 하락", "리튬", "희토류", "rare earth",
                          "commodity price", "원재료 가격", "소재 가격"]

GEOPOLITICAL_KEYWORDS = ["리쇼어링", "reshoring", "국산화", "localization",
                          "미중 갈등", "US-China", "탈중국", "공급망 재편",
                          "supply chain", "IRA", "CHIPS Act", "반도체법"]

SPINOFF_KEYWORDS = ["분할", "spinoff", "물적분할", "분사", "지주회사",
                    "구조조정", "restructuring", "사업 분리", "IPO 예정"]

EARNINGS_KEYWORDS = ["어닝 서프라이즈", "earnings surprise", "컨센서스 상회",
                     "beat estimate", "실적 호조", "예상치 초과", "깜짝 실적"]


def _extract_amount_krw(text: str) -> float | None:
    """Extract amount in KRW billions from Korean text."""
    # 조 단위 (trillion KRW)
    m = re.search(r"(\d+(?:\.\d+)?)\s*조\s*원?", text)
    if m:
        return float(m.group(1)) * 1_000_000  # billions

    # 억 단위 (100M KRW)
    m = re.search(r"(\d+(?:,\d{3})*(?:\.\d+)?)\s*억\s*원?", text)
    if m:
        val = float(m.group(1).replace(",", ""))
        return val / 10  # to billions

    return None


def _extract_amount_usd(text: str) -> float | None:
    """Extract amount in USD billions."""
    m = re.search(r"\$?\s*(\d+(?:\.\d+)?)\s*[Bb]illion", text)
    if m:
        return float(m.group(1))
    m = re.search(r"\$?\s*(\d+(?:\.\d+)?)\s*[Mm]illion", text)
    if m:
        return float(m.group(1)) / 1_000
    return None


def _keyword_hit(text: str, keywords: list[str]) -> list[str]:
    """Return matched keywords from list."""
    text_lower = text.lower()
    return [kw for kw in keywords if kw.lower() in text_lower]


def _confidence(hits: int, total: int, has_amount: bool) -> float:
    """Simple confidence score 0-1."""
    base = min(1.0, hits / max(1, total * 0.3))
    if has_amount:
        base = min(1.0, base + 0.2)
    return round(base, 2)


@dataclass
class TriggerResult:
    trigger_type: str
    confidence: float
    matched_keywords: list[str] = field(default_factory=list)
    parsed_amount: float | None = None
    summary: str = ""


def classify(text: str, headline: str = "") -> list[TriggerResult]:
    """Classify text into matching trigger types.

    Returns list of TriggerResult sorted by confidence desc.
    """
    combined = f"{headline} {text}"
    results: list[TriggerResult] = []

    # 1. 단일_수주 — bigtech order
    hits = _keyword_hit(combined, BIGTECH_KEYWORDS)
    amount = _extract_amount_krw(combined) or _extract_amount_usd(combined)
    if hits:
        # Must mention an order/수주 word too
        order_words = ["수주", "계약", "contract", "order", "award", "공급"]
        if any(w.lower() in combined.lower() for w in order_words):
            conf = _confidence(len(hits), len(BIGTECH_KEYWORDS), amount is not None)
            if amount and amount >= 50:  # 50억+ or $50M+
                conf = min(1.0, conf + 0.15)
            results.append(TriggerResult(
                trigger_type="단일_수주",
                confidence=conf,
                matched_keywords=hits,
                parsed_amount=amount,
                summary=f"빅테크 수주: {', '.join(hits[:3])}",
            ))

    # 2. CAPEX_증설
    hits = _keyword_hit(combined, CAPEX_KEYWORDS)
    if hits:
        amount = _extract_amount_krw(combined) or _extract_amount_usd(combined)
        conf = _confidence(len(hits), len(CAPEX_KEYWORDS), amount is not None)
        results.append(TriggerResult(
            trigger_type="CAPEX_증설",
            confidence=conf,
            matched_keywords=hits,
            parsed_amount=amount,
            summary=f"설비 증설: {', '.join(hits[:3])}",
        ))

    # 3. 글로벌_메가계약
    hits = _keyword_hit(combined, GLOBAL_MEGA_KEYWORDS)
    if len(hits) >= 2:
        amount = _extract_amount_krw(combined) or _extract_amount_usd(combined)
        conf = _confidence(len(hits), len(GLOBAL_MEGA_KEYWORDS), amount is not None)
        results.append(TriggerResult(
            trigger_type="글로벌_메가계약",
            confidence=conf,
            matched_keywords=hits,
            parsed_amount=amount,
            summary=f"글로벌 계약: {', '.join(hits[:3])}",
        ))

    # 4. 빅테크_파트너
    hits_bt = _keyword_hit(combined, BIGTECH_KEYWORDS)
    hits_pt = _keyword_hit(combined, BIGTECH_PARTNER_KEYWORDS)
    if hits_bt and hits_pt:
        conf = _confidence(len(hits_bt) + len(hits_pt), 4, False)
        results.append(TriggerResult(
            trigger_type="빅테크_파트너",
            confidence=conf,
            matched_keywords=hits_bt[:2] + hits_pt[:2],
            summary=f"파트너십: {', '.join((hits_bt + hits_pt)[:3])}",
        ))

    # 5. 시장_독점
    hits = _keyword_hit(combined, MONOPOLY_KEYWORDS)
    if hits:
        conf = _confidence(len(hits), len(MONOPOLY_KEYWORDS), False)
        results.append(TriggerResult(
            trigger_type="시장_독점",
            confidence=conf,
            matched_keywords=hits,
            summary=f"독점 포지션: {', '.join(hits[:3])}",
        ))

    # 6. 기술_돌파
    hits = _keyword_hit(combined, TECH_BREAKTHROUGH_KEYWORDS)
    if hits:
        conf = _confidence(len(hits), len(TECH_BREAKTHROUGH_KEYWORDS), False)
        results.append(TriggerResult(
            trigger_type="기술_돌파",
            confidence=conf,
            matched_keywords=hits,
            summary=f"기술 돌파: {', '.join(hits[:3])}",
        ))

    # 7. 수익성_급등
    hits = _keyword_hit(combined, PROFITABILITY_KEYWORDS)
    if hits:
        conf = _confidence(len(hits), len(PROFITABILITY_KEYWORDS), False)
        results.append(TriggerResult(
            trigger_type="수익성_급등",
            confidence=conf,
            matched_keywords=hits,
            summary=f"수익성 개선: {', '.join(hits[:3])}",
        ))

    # 8. 내부자_매수
    hits = _keyword_hit(combined, INSIDER_BUY_KEYWORDS)
    if hits:
        conf = _confidence(len(hits), len(INSIDER_BUY_KEYWORDS), False)
        results.append(TriggerResult(
            trigger_type="내부자_매수",
            confidence=conf,
            matched_keywords=hits,
            summary=f"내부자 매수: {', '.join(hits[:3])}",
        ))

    # 9. 기관_집중
    hits = _keyword_hit(combined, INSTITUTIONAL_KEYWORDS)
    if hits:
        conf = _confidence(len(hits), len(INSTITUTIONAL_KEYWORDS), False)
        results.append(TriggerResult(
            trigger_type="기관_집중",
            confidence=conf,
            matched_keywords=hits,
            summary=f"기관 집중: {', '.join(hits[:3])}",
        ))

    # 10. 규제_해소
    hits = _keyword_hit(combined, REGULATORY_KEYWORDS)
    if hits:
        conf = _confidence(len(hits), len(REGULATORY_KEYWORDS), False)
        results.append(TriggerResult(
            trigger_type="규제_해소",
            confidence=conf,
            matched_keywords=hits,
            summary=f"규제 해소: {', '.join(hits[:3])}",
        ))

    # 11. 공급_병목
    hits = _keyword_hit(combined, SUPPLY_BOTTLENECK_KEYWORDS)
    if hits:
        conf = _confidence(len(hits), len(SUPPLY_BOTTLENECK_KEYWORDS), False)
        results.append(TriggerResult(
            trigger_type="공급_병목",
            confidence=conf,
            matched_keywords=hits,
            summary=f"공급 병목: {', '.join(hits[:3])}",
        ))

    # 12. 원자재_가격
    hits = _keyword_hit(combined, RAW_MATERIAL_KEYWORDS)
    if hits:
        conf = _confidence(len(hits), len(RAW_MATERIAL_KEYWORDS), False)
        results.append(TriggerResult(
            trigger_type="원자재_가격",
            confidence=conf,
            matched_keywords=hits,
            summary=f"원자재 가격: {', '.join(hits[:3])}",
        ))

    # 13. 지정학_수혜
    hits = _keyword_hit(combined, GEOPOLITICAL_KEYWORDS)
    if hits:
        conf = _confidence(len(hits), len(GEOPOLITICAL_KEYWORDS), False)
        results.append(TriggerResult(
            trigger_type="지정학_수혜",
            confidence=conf,
            matched_keywords=hits,
            summary=f"지정학 수혜: {', '.join(hits[:3])}",
        ))

    # 14. 스핀오프
    hits = _keyword_hit(combined, SPINOFF_KEYWORDS)
    if hits:
        conf = _confidence(len(hits), len(SPINOFF_KEYWORDS), False)
        results.append(TriggerResult(
            trigger_type="스핀오프",
            confidence=conf,
            matched_keywords=hits,
            summary=f"구조 재편: {', '.join(hits[:3])}",
        ))

    # 15. 실적_서프라이즈
    hits = _keyword_hit(combined, EARNINGS_KEYWORDS)
    if hits:
        conf = _confidence(len(hits), len(EARNINGS_KEYWORDS), False)
        results.append(TriggerResult(
            trigger_type="실적_서프라이즈",
            confidence=conf,
            matched_keywords=hits,
            summary=f"실적 서프라이즈: {', '.join(hits[:3])}",
        ))

    results.sort(key=lambda r: r.confidence, reverse=True)
    return results


def classify_filing(filing: dict) -> list[TriggerResult]:
    """Classify a filing dict (with 'headline' and 'raw_text' keys)."""
    headline = filing.get("headline", "")
    text = filing.get("raw_text", "")
    results = classify(text, headline)
    if results:
        logger.info(
            "Filing %s → %d triggers (top: %s %.0f%%)",
            filing.get("id", "?"),
            len(results),
            results[0].trigger_type,
            results[0].confidence * 100,
        )
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sample = "SK하이닉스, NVIDIA에 600억원 규모 TC본더 수주 계약 체결"
    results = classify(sample)
    for r in results:
        print(r)
