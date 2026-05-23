"""한국어 금융 도메인 키워드 사전 (KR Finance Lexicon).

Loughran-McDonald (2011) 방식으로 KR 공시/뉴스 도메인에 맞게 구성.
일반 감성사전(Harvard General Inquirer)이 finance에서 75% 오분류 → KR도 동일 문제.

카테고리별:
  - POSITIVE: 해당 카테고리에서 상승을 예고하는 핵심 키워드
  - NEGATIVE: refutation 신호 (부정적, 위험)
  - SECTOR_SIGNALS: 섹터/테마 분류 신호

DART 공시 종류별 시그널 (report_type_signals):
  - 단일판매공급계약 → 수주잔고_선행
  - 유상증자 → 희석 (refutation)
  - 임상시험결과 → 임상_파이프라인
  - 기술이전계약 → 임상_파이프라인 or 빅테크_파트너
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CategoryLexicon:
    category: str
    positive: list[str]        # 매수 시그널 키워드
    negative: list[str]        # refutation 키워드
    sector_signals: list[str]  # 섹터 분류용
    dart_triggers: list[str]   # DART 공시 코드 또는 공시명 포함 키워드


LEXICON: dict[str, CategoryLexicon] = {
    "수주잔고_선행": CategoryLexicon(
        category="수주잔고_선행",
        positive=[
            "수주", "계약체결", "수주잔고", "잔고", "공급계약", "납품계약",
            "수주액", "계약금액", "수주총액", "megadeal", "대형계약",
            "장기공급", "프레임워크계약", "마스터공급계약",
            "backlog", "order book", "수주규모", "수주현황",
            "단일판매공급계약", "공급협약", "LOI", "MOU체결",
            "수주잔액", "잔여계약", "실행계약",
        ],
        negative=[
            "계약해지", "계약취소", "수주취소", "반품", "리콜",
            "수주감소", "수주부진", "계약지연", "납기지연",
        ],
        sector_signals=["방산", "조선", "건설", "플랜트", "중공업", "IT서비스", "반도체장비"],
        dart_triggers=[
            "단일판매공급계약체결",  # DART 공시명
            "수주공시", "공급계약", "장기공급계약",
        ],
    ),

    "수익성_급전환": CategoryLexicon(
        category="수익성_급전환",
        positive=[
            "영업이익", "영업이익률", "흑자전환", "적자탈출", "턴어라운드",
            "수익성 개선", "마진 개선", "원가절감", "구조조정", "체질개선",
            "고부가제품", "믹스개선", "ASP 상승", "판가인상",
            "고정비레버리지", "손익분기점", "BEP 달성",
            "operating leverage", "margin expansion",
        ],
        negative=[
            "영업손실", "적자지속", "영업이익 감소", "마진압박",
            "원가상승", "가격인하", "경쟁심화", "수익성 악화",
        ],
        sector_signals=["제조", "화학", "소재", "디스플레이", "반도체"],
        dart_triggers=["영업실적발표", "잠정실적"],
    ),

    "빅테크_파트너": CategoryLexicon(
        category="빅테크_파트너",
        positive=[
            "전략적투자", "지분취득", "콜옵션", "지분투자",
            "삼성전자", "LG전자", "SK하이닉스", "현대차",
            "NVIDIA", "Apple", "Google", "Microsoft", "Amazon", "Meta",
            "파트너십", "전략적파트너", "공동개발", "독점공급",
            "벤더등록", "공급업체선정", "Tier1", "preferred vendor",
            "strategic alliance", "exclusive supply",
        ],
        negative=[
            "파트너십해지", "공급계약취소", "벤더제외",
            "경쟁업체선정", "대체공급사",
        ],
        sector_signals=["반도체", "디스플레이", "배터리", "로봇", "AI"],
        dart_triggers=["전략적투자유치", "지분취득공시", "공동개발계약"],
    ),

    "플랫폼_독점": CategoryLexicon(
        category="플랫폼_독점",
        positive=[
            "독점", "유일한", "글로벌유일", "세계최초", "특허", "기술장벽",
            "진입장벽", "시장지배", "독점적위치", "국내유일",
            "수직계열화", "일관생산", "원스탑", "풀라인업",
            "시장점유율", "MS확대", "lock-in", "플랫폼",
            "생태계", "표준", "de facto standard",
        ],
        negative=[
            "경쟁자진입", "특허무효", "독점해소", "시장점유율하락",
            "중국경쟁", "저가공세", "기술추격",
        ],
        sector_signals=["반도체장비", "광섬유", "소부장", "플랫폼"],
        dart_triggers=["특허등록", "기술인증획득"],
    ),

    "정책_수혜": CategoryLexicon(
        category="정책_수혜",
        positive=[
            "IRA", "인플레이션감축법", "CHIPS Act", "칩스법",
            "정책수혜", "보조금", "세액공제", "R&D지원",
            "방위비", "국방예산", "K-방산", "재무장",
            "원전", "SMR", "소형원전", "핵발전",
            "탄소중립", "RE100", "그린뉴딜", "탄소세",
            "K-뉴딜", "디지털뉴딜", "규제완화",
            "정부계약", "공공조달", "나라장터",
        ],
        negative=[
            "규제강화", "세금인상", "보조금축소", "예산삭감",
            "정책리스크", "규제위반", "과징금",
        ],
        sector_signals=["방산", "에너지", "전력", "태양광", "풍력", "원전"],
        dart_triggers=["정부계약체결", "공공조달계약"],
    ),

    "공급_병목": CategoryLexicon(
        category="공급_병목",
        positive=[
            "공급부족", "납기지연", "리드타임", "lead time",
            "수요급증", "수요폭발", "capacity 부족",
            "증설", "CAPEX", "설비투자", "공장증설",
            "병목현상", "supply chain", "공급망이슈",
            "전방산업성장", "downstream demand",
            "가동률", "가동률상승", "풀가동",
        ],
        negative=[
            "공급과잉", "재고증가", "수요둔화", "단가하락",
            "증설취소", "투자철회",
        ],
        sector_signals=["반도체", "배터리소재", "희토류", "광섬유", "전력기기"],
        dart_triggers=["공장신설", "설비투자결정", "생산능력확대"],
    ),

    "임상_파이프라인": CategoryLexicon(
        category="임상_파이프라인",
        positive=[
            "FDA", "IND", "NDA", "BLA", "허가신청",
            "임상", "임상시험", "Phase 1", "Phase 2", "Phase 3",
            "임상성공", "유효성확인", "주요평가변수달성",
            "기술이전", "라이선스아웃", "license-out",
            "milestone", "계약금", "upfront",
            "바이오시밀러", "ADC", "mRNA", "CAR-T",
            "희귀의약품", "orphan drug", "fast track",
        ],
        negative=[
            "임상실패", "임상중단", "FDA거절", "CRL",
            "부작용", "독성", "안전성우려",
            "경쟁약물승인", "특허만료",
        ],
        sector_signals=["제약", "바이오", "의료기기", "헬스케어"],
        dart_triggers=[
            "임상시험결과발표", "의약품허가신청",
            "기술이전계약", "라이선스계약",
        ],
    ),
}

# DART 공시 코드 → 카테고리 매핑 (주요사항보고서 기준)
DART_REPORT_TYPE_SIGNALS: dict[str, str] = {
    "단일판매·공급계약체결": "수주잔고_선행",
    "단일판매·공급계약해지": "_negative",
    "유상증자결정": "_dilution",
    "전환사채권발행결정": "_dilution",
    "신주인수권부사채권발행결정": "_dilution",
    "임상시험결과발표": "임상_파이프라인",
    "기술이전계약체결": "임상_파이프라인",
    "전략적투자": "빅테크_파트너",
    "주요계약체결": "수주잔고_선행",
    "연구개발결과발표": "임상_파이프라인",
}


def get_lexicon(category: str) -> CategoryLexicon | None:
    return LEXICON.get(category)


def score_text_for_category(
    text: str,
    category: str,
    min_positive: int = 2,
) -> dict:
    """텍스트에서 카테고리별 키워드 점수 계산.

    Returns:
        {"positive_hits": [...], "negative_hits": [...], "score": float, "is_match": bool}
    """
    lex = LEXICON.get(category)
    if not lex:
        return {"positive_hits": [], "negative_hits": [], "score": 0.0, "is_match": False}

    text_lower = text.lower()
    pos_hits = [kw for kw in lex.positive if kw.lower() in text_lower]
    neg_hits = [kw for kw in lex.negative if kw.lower() in text_lower]

    # 점수: positive +1, negative -0.5
    score = len(pos_hits) - 0.5 * len(neg_hits)
    is_match = len(pos_hits) >= min_positive

    return {
        "positive_hits": pos_hits,
        "negative_hits": neg_hits,
        "score": round(score, 2),
        "is_match": is_match,
    }


def classify_dart_report(report_type: str) -> tuple[str, bool]:
    """DART 공시 종류 → (카테고리, is_negative) 분류.

    Returns: ("수주잔고_선행", False) 또는 ("_dilution", True) 등.
    """
    for pattern, cat in DART_REPORT_TYPE_SIGNALS.items():
        if pattern in report_type:
            is_neg = cat.startswith("_")
            return cat, is_neg
    return "unknown", False


def detect_refutation_from_report(report_type: str, text: str) -> bool:
    """공시 내용에서 refutation 시그널 감지."""
    _, is_neg = classify_dart_report(report_type)
    if is_neg:
        return True
    # 텍스트 기반 refutation 키워드
    refutation_keywords = [
        "계약해지", "계약취소", "파산", "워크아웃", "법정관리",
        "상장폐지예고", "감사의견거절", "횡령", "배임",
    ]
    text_lower = text.lower()
    return any(kw in text_lower for kw in refutation_keywords)
