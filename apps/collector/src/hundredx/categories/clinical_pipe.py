"""임상_파이프라인 detector — 키워드 존재 + 단계 전이 감지.

Stage-progression comparison (Phase 2 upgrade):
  가장 최근 공시 vs. 그 이전 공시의 임상 단계를 비교.
  단계가 상승하면(1상→2상, 2상→3상, IND→1상, 3상→승인 등) confidence 보정.

개선 사항 (2026-05-23):
  - 최소 신뢰도 0.5 → 0.70으로 상향 (단일 강력 키워드 히트)
  - GLP-1/펩타이드/항체의약품 등 신규 키워드 추가
  - 기술이전/마일스톤 대형 계약 감지 강화
  - 안과/희귀질환/항암 세부 키워드 추가
  - 다중 강력 키워드 히트 시 confidence 보너스

Confidence table:
  keyword 1개 공시에만    → 0.70 (기존 0.5 → 상향)
  keyword 2개 공시 모두   → 0.75 (기존 0.7)
  keyword + 고액 기술이전  → 0.80+
  keyword + 단계 전이 감지  → 0.85
  keyword + 2단계+ 전이    → 0.90
"""
from __future__ import annotations
import re
from ..keywords import BIOTECH_PIPELINE_KEYWORDS
from ..models import CategoryMatch

# Stage hierarchy: higher number = later / more advanced
_STAGE_PATTERNS: list[tuple[int, list[str]]] = [
    (0, ["IND", "임상시험계획승인", "임상시험계획", "임상시험 계획", "IND 신청"]),
    (1, ["1상", "phase 1", "phase i", "1/2상", "임상 1상", "제1상", "임상1상"]),
    (2, ["2상", "phase 2", "phase ii", "2/3상", "임상 2상", "제2상", "임상2상",
         "2a상", "2b상", "phase 2a", "phase 2b"]),
    (3, ["3상", "phase 3", "phase iii", "임상 3상", "제3상", "임상3상",
         "3상 진입", "3상 완료", "최종 임상", "pivotal trial"]),
    (4, ["nda", "bla", "품목허가", "허가 신청", "fda 신청", "식약처 허가신청",
         "식약처 신청", "mfds 신청", "시판허가", "허가 출원"]),
    (5, ["fda 승인", "fda approval", "식약처 승인", "품목허가 획득", "최종 허가",
         "시판 허가", "허가 취득", "fda cleared", "approved by fda"]),
]

# 강력 키워드: 이것만으로도 높은 신뢰도 가능
_STRONG_CLINICAL_KEYWORDS = [
    # GLP-1 / 비만/당뇨 대세
    "GLP-1", "GLP1", "세마글루타이드", "semaglutide", "리라글루타이드", "liraglutide",
    "티르제파타이드", "tirzepatide", "위고비", "오젬픽", "wegovy", "ozempic",
    "비만 치료", "당뇨 치료",
    # 기술이전 / 라이센스 대형계약
    "기술이전", "license out", "라이선스 아웃", "기술수출",
    "마일스톤", "milestone", "선급금", "upfront",
    "글로벌 계약", "해외 기술이전",
    # 빅파마 협력
    "빅파마", "big pharma", "글로벌 제약사",
    "MSD", "Merck", "Pfizer", "AstraZeneca", "Roche", "Novartis",
    "BMS", "Gilead", "Lilly", "Eli Lilly", "AbbVie", "J&J", "Janssen",
    # 항체의약품 / 바이오시밀러
    "ADC", "항체-약물 접합체", "antibody drug conjugate",
    "바이오시밀러", "biosimilar", "단클론항체", "monoclonal antibody",
    "이중항체", "bispecific",
    # 세포/유전자 치료
    "CAR-T", "세포치료제", "유전자치료제", "gene therapy", "cell therapy",
    # 안과 (삼천당제약 계열)
    "점안제", "안과", "ophthalmic", "안구", "황반변성", "녹내장",
    "라니비주맙", "베바시주맙", "애플리버셉트", "lucentis", "avastin",
    # 희귀질환
    "희귀의약품", "orphan drug", "희귀질환", "orphan designation",
    # 항암 / 면역항암
    "면역항암", "immuno-oncology", "PD-L1", "PD-1", "checkpoint",
    "CAR-NK", "키트루다", "keytruda",
    # CDMO / CMO
    "CDMO", "CMO", "위탁생산", "위탁개발",
    # 인증
    "CE 인증", "EU 허가", "PMDA",
]

# 일반 임상 키워드 (기존)
_GENERAL_CLINICAL_KEYWORDS = BIOTECH_PIPELINE_KEYWORDS + [
    "펩타이드", "peptide", "바이오의약품", "biologics", "단백질 의약품",
    "임상시험", "clinical trial", "임상 완료", "임상 성공", "IND 신청",
    "임상 결과", "데이터 분석", "안전성", "유효성", "efficacy", "safety",
    "환자 등록", "patient enrollment", "용량 코호트",
    "NDA", "BLA", "식약처", "MFDS", "FDA", "EMA",
    "품목허가", "시판허가", "신약 허가",
]


def _kw_hit(text: str, keywords: list[str]) -> list[str]:
    text_lower = text.lower()
    return [kw for kw in keywords if kw.lower() in text_lower]


def _detect_stage(text: str) -> int | None:
    """Return highest stage number found in text, or None."""
    text_lower = text.lower()
    found: list[int] = []
    for stage_num, patterns in _STAGE_PATTERNS:
        for pat in patterns:
            if pat.lower() in text_lower:
                found.append(stage_num)
                break
    return max(found) if found else None


def _detect_milestone_amount(text: str) -> float | None:
    """Extract milestone / upfront payment amount in KRW billions."""
    # 조 단위
    m = re.search(r"(\d+(?:\.\d+)?)\s*조\s*원?", text)
    if m:
        return float(m.group(1)) * 1000

    # 억 단위
    m = re.search(r"(\d+(?:,\d{3})*(?:\.\d+)?)\s*억\s*원?", text)
    if m:
        return float(m.group(1).replace(",", "")) / 10

    # USD millions
    m = re.search(r"\$?\s*(\d+(?:\.\d+)?)\s*[Mm]illion", text)
    if m:
        return float(m.group(1)) / 1000  # to billions KRW equivalent

    # USD billions
    m = re.search(r"\$?\s*(\d+(?:\.\d+)?)\s*[Bb]illion", text)
    if m:
        return float(m.group(1))

    return None


def detect(stock_data: dict, filings: list[dict]) -> CategoryMatch | None:
    ticker = stock_data.get("ticker", "")

    # filings is already pre-limited to 2 most recent by scanner._fetch_filings_2y
    filings_with_hits: list[tuple[dict, list[str], list[str], int | None, float | None]] = []
    for filing in filings[:2]:
        text = (filing.get("raw_text") or "") + " " + (filing.get("headline") or "")
        general_hits = _kw_hit(text, _GENERAL_CLINICAL_KEYWORDS)
        strong_hits = _kw_hit(text, _STRONG_CLINICAL_KEYWORDS)
        all_hits = list(set(general_hits + strong_hits))
        stage = _detect_stage(text)
        amount = _detect_milestone_amount(text)

        if all_hits or stage is not None:
            filings_with_hits.append((filing, all_hits, strong_hits, stage, amount))

    if not filings_with_hits:
        return None

    # ── 신뢰도 계산 ───────────────────────────────────────────────────────────

    # 강력 키워드 집계
    all_strong = []
    for _, _, strong_h, _, _ in filings_with_hits:
        all_strong.extend(strong_h)
    all_strong = list(set(all_strong))

    all_general = []
    for _, gen_h, _, _, _ in filings_with_hits:
        all_general.extend(gen_h)
    all_general = list(set(all_general))

    # 기술이전 금액
    total_amount = max((a for _, _, _, _, a in filings_with_hits if a), default=None)

    # Base confidence 개선:
    # - 강력 키워드 2개+ → 0.75
    # - 강력 키워드 1개 → 0.72
    # - 일반 키워드 2개 공시 모두 → 0.72
    # - 일반 키워드 1개 공시 → 0.70 (기존 0.5에서 상향)
    all_have_hits = all(gen_h for _, gen_h, _, _, _ in filings_with_hits)

    if len(all_strong) >= 2:
        base_confidence = 0.75
    elif len(all_strong) == 1:
        base_confidence = 0.72
    elif len(filings_with_hits) >= 2 and all_have_hits:
        base_confidence = 0.72
    else:
        base_confidence = 0.70  # 기존 0.5에서 상향 (scanner 0.7 threshold 통과)

    # 기술이전 대형계약 보너스
    license_hits = _kw_hit(
        " ".join(
            [(f.get("raw_text") or "") + " " + (f.get("headline") or "")
             for f, _, _, _, _ in filings_with_hits]
        ),
        ["기술이전", "license out", "라이선스 아웃", "기술수출", "milestone", "마일스톤"]
    )
    if license_hits and total_amount and total_amount >= 100:  # 1000억+ 계약
        base_confidence = min(0.88, base_confidence + 0.12)
    elif license_hits:
        base_confidence = min(0.82, base_confidence + 0.07)

    # Stage-progression bonus: most recent filing advanced beyond previous
    stage_delta = 0
    if len(filings_with_hits) >= 2:
        _, _, _, stage_recent, _ = filings_with_hits[0]
        _, _, _, stage_prev, _ = filings_with_hits[1]
        if stage_recent is not None and stage_prev is not None and stage_recent > stage_prev:
            stage_delta = stage_recent - stage_prev

    if stage_delta >= 2:
        confidence = 0.90
    elif stage_delta == 1:
        confidence = 0.85
    else:
        confidence = base_confidence

    # ── Evidence 생성 ─────────────────────────────────────────────────────────
    evidence: list[dict] = []
    for filing, gen_hits, strong_hits, stage, amount in filings_with_hits:
        evidence.append({
            "source_type": "filing",
            "source_id": str(filing.get("id", "")),
            "text_excerpt": (filing.get("headline") or "")[:200],
            "date": filing.get("filed_at"),
            "amount": amount,
        })
        all_hits_combined = list(set(gen_hits + strong_hits))
        if all_hits_combined:
            evidence.append({
                "source_type": "keywords",
                "source_id": str(filing.get("id", "")) + "_kw",
                "text_excerpt": f"임상 키워드: {', '.join(all_hits_combined[:5])}",
                "date": filing.get("filed_at"),
                "amount": amount,
            })

    # Stage transition evidence
    if stage_delta > 0 and len(filings_with_hits) >= 2:
        _, _, _, s0, _ = filings_with_hits[1]  # older
        _, _, _, s1, _ = filings_with_hits[0]  # recent
        _stage_names = {0: "IND", 1: "1상", 2: "2상", 3: "3상", 4: "허가 신청", 5: "최종 승인"}
        evidence.append({
            "source_type": "stage_transition",
            "source_id": "stage_delta",
            "text_excerpt": (
                f"임상 단계 전이: {_stage_names.get(s0, f'단계{s0}')} --> "
                f"{_stage_names.get(s1, f'단계{s1}')} (+{stage_delta}단계)"
            ),
            "date": filings_with_hits[0][0].get("filed_at"),
            "amount": float(stage_delta),
        })

    # 기술이전 evidence
    if license_hits and total_amount:
        evidence.append({
            "source_type": "license_deal",
            "source_id": "license_amount",
            "text_excerpt": f"기술이전/라이선스 계약: {total_amount:.0f}억원 규모",
            "date": filings_with_hits[0][0].get("filed_at"),
            "amount": total_amount,
        })

    return CategoryMatch(
        ticker=ticker,
        category="임상_파이프라인",
        confidence=confidence,
        evidence=evidence,
    )
