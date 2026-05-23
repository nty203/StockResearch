"""빅테크_파트너 detector — BigTech equity stake + call option or high-profile supply contract.

개선 사항 (2026-05-23):
  - 1. 기존 지분 취득 및 콜옵션 투자 구조 (conf = 0.70 ~ 0.90) 유지
  - 2. 신규: 글로벌 빅테크/선도기업과의 대형 공급/협력 계약 포착 (conf = 0.75)
    - BIGTECH_KEYWORDS + 공급/협력 키워드 + 핵심 섹터 매칭 시 인정
  - 3. 강화: 로봇/자동화 섹터 추가 (레인보우로보틱스 등)
  - 4. 강화: 하이퍼스케일러 PCB/기판 공급 포착 (이수페타시스 등)
  - 5. 강화: 삼성/LG/SK 계열사 전략투자 포착
"""
from __future__ import annotations
from ..keywords import BIGTECH_KEYWORDS
from ..models import CategoryMatch

_EQUITY_KEYWORDS = [
    # Korean
    "유상증자 참여", "지분 취득", "전략적 투자", "지분 인수", "3자배정",
    "3자배정 유상증자", "최대주주 변경", "최대주주 등극", "최대주주로",
    "지분율", "콜옵션 행사", "풋옵션",
    # English
    "equity investment", "strategic investment", "acquired stake",
    "stake acquisition", "strategic partnership agreement",
    "equity stake", "share acquisition",
]

_CALLOPT_KEYWORDS = [
    # Korean
    "콜옵션", "최대주주 전환", "전환사채 취득", "자회사 편입",
    # English
    "call option", "warrant", "option to acquire",
    "right to purchase", "controlling interest", "conversion right",
]

_SUPPLY_KEYWORDS = [
    # Korean
    "공급", "계약", "납품", "협력", "파트너십", "수주", "개발",
    "우선 공급", "독점 공급", "납품 계약", "양산", "공급 계약 체결",
    "중장기 공급", "전략적 협력", "공급망 편입", "벤더 선정",
    "MOU", "업무협약",
    # English
    "supply", "contract", "partnership", "agreement", "deliver", "co-develop",
    "sole supplier", "exclusive contract", "preferred vendor",
    "supply agreement", "long-term supply", "volume agreement",
]

# 하이퍼스케일러/CSP 키워드 (이수페타시스, PCB/기판 공급 포착용)
_HYPERSCALER_SUPPLY_KEYWORDS = [
    # PCB/기판 관련
    "고다층", "MLB", "다층PCB", "기판", "패키지기판",
    "HDI", "FC-BGA", "서버용", "AI 서버", "GPU 서버",
    "데이터센터", "hyperscaler", "하이퍼스케일",
    # 냉각/열관리
    "액침냉각", "직접수냉", "liquid cooling", "immersion",
    # 전력 인프라
    "전력기기", "변압기", "UPS", "PDU",
]

_BIGTECH_SECTORS = {
    # 기존 섹터
    "반도체", "전력기기", "냉각", "열관리", "조선", "엔진", "방산",
    "semiconductor", "power", "cooling", "engine", "defense",
    # 신규: 로봇/자동화 (레인보우로보틱스 등)
    "로봇", "로보틱스", "협동로봇", "휴머노이드", "자동화", "robot", "automation",
    # 신규: PCB/기판 (이수페타시스 등)
    "pcb", "기판", "인쇄회로", "회로기판",
    # 신규: AI 인프라
    "ai 인프라", "데이터센터", "서버", "storage",
}

# 삼성/LG/SK 그룹 전략 투자사 키워드 (별도로 높은 가중치)
_KR_BIGTECH_INVESTORS = [
    "삼성전자", "삼성그룹", "삼성", "SK하이닉스", "SK이노베이션",
    "LG에너지솔루션", "LG전자", "현대차", "현대모비스", "기아",
    "네이버", "카카오", "롯데", "포스코",
]


def _kw_hit(text: str, keywords: list[str]) -> list[str]:
    text_lower = text.lower()
    return [kw for kw in keywords if kw.lower() in text_lower]


def detect(stock_data: dict, filings: list[dict]) -> CategoryMatch | None:
    ticker = stock_data.get("ticker", "")
    sector_tag = (stock_data.get("sector_tag") or "").lower()
    in_target_sector = any(s.lower() in sector_tag for s in _BIGTECH_SECTORS)

    best_confidence = 0.0
    best_evidence: list[dict] = []

    for filing in filings:
        text = (filing.get("raw_text") or "") + " " + (filing.get("headline") or "")
        if not text.strip():
            continue

        bigtech_hits = _kw_hit(text, BIGTECH_KEYWORDS)
        kr_investor_hits = _kw_hit(text, _KR_BIGTECH_INVESTORS)
        all_bigtech_hits = list(set(bigtech_hits + kr_investor_hits))

        if not all_bigtech_hits:
            continue

        equity_hits = _kw_hit(text, _EQUITY_KEYWORDS)
        callopt_hits = _kw_hit(text, _CALLOPT_KEYWORDS)
        supply_hits = _kw_hit(text, _SUPPLY_KEYWORDS)
        hyperscaler_hits = _kw_hit(text, _HYPERSCALER_SUPPLY_KEYWORDS)

        # ── 1차: 지분 취득 및 콜옵션 투자 구조 (M&A) ─────────────────
        if equity_hits and callopt_hits:
            conf = 0.90
        elif equity_hits:
            # 한국 대기업의 전략적 지분 투자 (삼성전자의 레인보우로보틱스 지분 취득 등)
            if kr_investor_hits:
                conf = 0.80  # KR 대기업 지분 취득은 더 높은 신뢰도
            else:
                conf = 0.70
        elif callopt_hits:
            conf = 0.70
        # ── 2차: 대형 빅테크 대상 공급/협력 계약 + 핵심 섹터 ──────────
        elif supply_hits and in_target_sector:
            conf = 0.75
        # ── 3차: 하이퍼스케일러 공급망 편입 (PCB/서버 부품 등) ────────
        elif hyperscaler_hits and (bigtech_hits or kr_investor_hits):
            conf = 0.72
        else:
            continue

        # 섹터 보너스 (+0.05)
        if in_target_sector and conf < 0.90:
            conf = min(0.90, conf + 0.05)

        # 콜옵션 추가 보너스 (+0.05): 미래 지배구조 변화 예고
        if callopt_hits and conf < 0.90:
            conf = min(0.90, conf + 0.05)

        if conf > best_confidence:
            best_confidence = conf
            evidence_entry = {
                "source_type": "filing",
                "source_id": str(filing.get("id", "")),
                "text_excerpt": (filing.get("headline") or "")[:200],
                "date": filing.get("filed_at"),
                "amount": None,
            }
            detail_entries = []
            if callopt_hits:
                detail_entries.append({
                    "source_type": "keywords",
                    "source_id": str(filing.get("id", "")) + "_callopt",
                    "text_excerpt": f"콜옵션/투자 조건: {', '.join(callopt_hits[:2])}",
                    "date": filing.get("filed_at"),
                    "amount": None,
                })
            if equity_hits:
                detail_entries.append({
                    "source_type": "keywords",
                    "source_id": str(filing.get("id", "")) + "_equity",
                    "text_excerpt": (
                        f"지분투자: {', '.join(equity_hits[:2])} | "
                        f"투자사: {', '.join(all_bigtech_hits[:2])}"
                    ),
                    "date": filing.get("filed_at"),
                    "amount": None,
                })
            elif supply_hits or hyperscaler_hits:
                all_supply = supply_hits + hyperscaler_hits
                detail_entries.append({
                    "source_type": "keywords",
                    "source_id": str(filing.get("id", "")) + "_supply",
                    "text_excerpt": (
                        f"공급/개발 협업: {', '.join(all_supply[:2])} | "
                        f"빅테크: {', '.join(all_bigtech_hits[:2])}"
                    ),
                    "date": filing.get("filed_at"),
                    "amount": None,
                })
            best_evidence = [evidence_entry] + detail_entries

    if best_confidence == 0.0:
        return None

    return CategoryMatch(
        ticker=ticker,
        category="빅테크_파트너",
        confidence=best_confidence,
        evidence=best_evidence,
    )
