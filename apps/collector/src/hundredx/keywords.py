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
                     "하이퍼스케일", "하이퍼스케일러", "빅테크", "CSP",
                     "삼성전자", "SK하이닉스", "LG전자"]

CAPEX_KEYWORDS = ["증설", "신공장", "CAPEX", "설비투자", "ground breaking",
                  "groundbreaking", "착공", "공장 건설", "생산라인", "라인 증설",
                  "capacity expansion", "new facility", "manufacturing expansion",
                  "생산능력", "capa", "캐파"]

GLOBAL_MEGA_KEYWORDS = ["방산", "원전", "SMR", "nuclear", "defense", "NATO",
                         "방위", "국방", "수출", "해외 수주", "overseas contract",
                         "조원", "trillion won", "billion dollar",
                         # 방산 하드웨어
                         "K-9", "K-2", "FA-50", "Redback", "자주포", "폴란드", "호주", "루마니아",
                         "방위산업", "무기 수출",
                         # 원전 세부
                         "APR-1400", "계측제어", "MMIS", "체코", "두코바니", "원안위",
                         # 전력기기
                         "HVDC", "GIS", "초고압", "변압기", "납기 확정", "전력기자재"]

BIGTECH_PARTNER_KEYWORDS = ["전략적 파트너십", "strategic partnership", "MOU",
                              "공급 계약", "supply agreement", "preferred supplier",
                              "독점 공급", "exclusive supply", "벤더 선정",
                              # 전략적 지분투자 (vs. 단순 재무투자)
                              "전략적 투자", "유상증자 참여", "콜옵션", "call option",
                              "지분 취득", "최대주주", "자회사 편입"]

# 바이오/제약 임상 파이프라인 키워드
BIOTECH_PIPELINE_KEYWORDS = ["임상", "1상", "2상", "3상", "IND", "임상시험계획",
                               "FDA 승인", "FDA approval", "식약처", "MFDS",
                               "기술이전", "license out", "마일스톤", "milestone",
                               "GLP-1", "세마글루타이드", "CDMO", "빅파마",
                               "품목허가", "NDA", "BLA", "CE 인증"]

# 로봇/자동화 생태계 키워드
ROBOTICS_ECOSYSTEM_KEYWORDS = ["협동로봇", "휴머노이드", "humanoid", "다이나믹셀",
                                 "액추에이터", "actuator", "ROS", "로봇 밀도",
                                 "물류 자동화", "공장 자동화", "로봇 도입",
                                 "AI 로봇", "자율주행 로봇"]

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
                          "supply chain", "IRA", "CHIPS Act", "반도체법",
                          "NATO 재무장", "방산 수출 확대", "원전 르네상스",
                          "에너지 안보", "AI 데이터센터 전력"]

SPINOFF_KEYWORDS = ["분할", "spinoff", "물적분할", "분사", "지주회사",
                    "구조조정", "restructuring", "사업 분리", "IPO 예정"]

EARNINGS_KEYWORDS = ["어닝 서프라이즈", "earnings surprise", "컨센서스 상회",
                     "beat estimate", "실적 호조", "예상치 초과", "깜짝 실적"]


def _extract_amount_krw(text: str) -> float | None:
    """Extract amount in KRW billions from Korean text."""
    # 조 단위 (trillion KRW): 1조 = 1,000 billion KRW
    m = re.search(r"(\d+(?:\.\d+)?)\s*조\s*원?", text)
    if m:
        return float(m.group(1)) * 1_000  # billions

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


# ── 트리거 유형 → 상승 원인 카테고리 매핑 ────────────────────────────────────
# 기본 매핑 — sector_tag 정보가 있으면 classify() 호출자가 덮어쓸 수 있음
TRIGGER_TO_RISE_CATEGORY: dict[str, str] = {
    "단일_수주":     "수주잔고_선행",
    "CAPEX_증설":    "수주잔고_선행",
    "글로벌_메가계약": "수주잔고_선행",
    "빅테크_파트너": "빅테크_파트너",
    "시장_독점":     "플랫폼_독점",
    "기술_돌파":     "플랫폼_독점",
    "수익성_급등":   "수익성_급전환",
    "내부자_매수":   "빅테크_파트너",
    "기관_집중":     "빅테크_파트너",
    "규제_해소":     "정책_수혜",
    "공급_병목":     "공급_병목",
    "원자재_가격":   "공급_병목",
    "지정학_수혜":   "정책_수혜",
    "스핀오프":      "수익성_급전환",
    "실적_서프라이즈": "수익성_급전환",
}


@dataclass
class TriggerResult:
    trigger_type: str
    confidence: float
    matched_keywords: list[str] = field(default_factory=list)
    parsed_amount: float | None = None
    summary: str = ""
    rise_category: str | None = None  # 상승 원인 카테고리


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

    # ── 확장 트리거: 플랫폼 기업 조기 포착용 ──────────────────────────────────

    # 전략적 지분투자 (콜옵션 포함 시 confidence 보너스)
    hits_bt = _keyword_hit(combined, BIGTECH_KEYWORDS)
    hits_pt = _keyword_hit(combined, BIGTECH_PARTNER_KEYWORDS)
    callopt_words = ["콜옵션", "call option", "최대주주 전환", "자회사 편입"]
    has_callopt = any(w.lower() in combined.lower() for w in callopt_words)
    if hits_bt and any(k in hits_pt for k in ["유상증자 참여", "지분 취득", "전략적 투자"]):
        conf = _confidence(len(hits_bt) + len(hits_pt), 5, False)
        if has_callopt:
            conf = min(1.0, conf + 0.25)  # 콜옵션 구조 = 미래 지배구조 변화 예고
        results.append(TriggerResult(
            trigger_type="빅테크_파트너",
            confidence=conf,
            matched_keywords=hits_bt[:2] + hits_pt[:2],
            summary=f"전략적 지분투자: {', '.join((hits_bt + hits_pt)[:3])}{'(+콜옵션)' if has_callopt else ''}",
        ))

    # 바이오 임상 파이프라인 진행 (기술_돌파 서브타입)
    hits = _keyword_hit(combined, BIOTECH_PIPELINE_KEYWORDS)
    if len(hits) >= 2:
        amount = _extract_amount_usd(combined) or _extract_amount_krw(combined)
        conf = _confidence(len(hits), len(BIOTECH_PIPELINE_KEYWORDS), amount is not None)
        if amount and amount >= 1000:  # 마일스톤 1000억+ or $100M+
            conf = min(1.0, conf + 0.2)
        results.append(TriggerResult(
            trigger_type="기술_돌파",
            confidence=conf,
            matched_keywords=hits,
            parsed_amount=amount,
            summary=f"바이오 임상/기술이전: {', '.join(hits[:3])}",
        ))

    # 로봇/자동화 생태계 채택 (공급_병목 또는 시장_독점 서브타입)
    hits = _keyword_hit(combined, ROBOTICS_ECOSYSTEM_KEYWORDS)
    if hits:
        hits_bigtech2 = _keyword_hit(combined, BIGTECH_KEYWORDS)
        conf = _confidence(len(hits), len(ROBOTICS_ECOSYSTEM_KEYWORDS), False)
        if hits_bigtech2:
            conf = min(1.0, conf + 0.15)  # 빅테크 로봇 채택
        results.append(TriggerResult(
            trigger_type="시장_독점",
            confidence=conf,
            matched_keywords=hits[:3],
            summary=f"로봇 생태계 채택: {', '.join(hits[:3])}",
        ))

    # rise_category 자동 할당
    for r in results:
        if r.rise_category is None:
            r.rise_category = TRIGGER_TO_RISE_CATEGORY.get(r.trigger_type)

    # 바이오 임상 키워드가 포함된 경우 임상_파이프라인으로 오버라이드
    biotech_hits = _keyword_hit(combined, BIOTECH_PIPELINE_KEYWORDS)
    if len(biotech_hits) >= 2:
        for r in results:
            if r.trigger_type in ("기술_돌파", "규제_해소", "실적_서프라이즈"):
                r.rise_category = "임상_파이프라인"

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
