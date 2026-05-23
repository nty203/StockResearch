"""Unit tests for the 7 hundredx category detectors.

All tests are pure — no DB calls, no external dependencies.
"""
import pytest

from src.hundredx.categories.backlog_lead import detect as detect_backlog
from src.hundredx.categories.profit_inflect import detect as detect_profit
from src.hundredx.categories.bigtech_partner import detect as detect_bigtech
from src.hundredx.categories.platform_mono import detect as detect_mono
from src.hundredx.categories.policy_benefit import detect as detect_policy
from src.hundredx.categories.supply_choke import detect as detect_supply
from src.hundredx.categories.clinical_pipe import detect as detect_clinical


# ── Helpers ───────────────────────────────────────────────────────────────────

def _filing(headline: str, raw_text: str = "", filing_id: str = "f1") -> dict:
    return {"id": filing_id, "ticker": "000000", "headline": headline,
            "raw_text": raw_text, "filed_at": "2025-01-01"}


# ── TestBacklogLead ───────────────────────────────────────────────────────────

class TestBacklogLead:
    def _stock(self, backlog, revenue_ttm, backlog_prev=None):
        return {
            "ticker": "TEST01",
            "order_backlog": backlog,
            "order_backlog_prev": backlog_prev,
            "revenue_ttm": revenue_ttm,
        }

    def test_high_bcr_returns_match(self):
        result = detect_backlog(self._stock(2_000, 1_000), [])
        assert result is not None
        assert result.confidence >= 0.7
        assert result.category == "수주잔고_선행"

    def test_bcr_below_threshold_no_match(self):
        # BCR = 1_200 / 1_000 = 1.2 → below 1.5
        result = detect_backlog(self._stock(1_200, 1_000), [])
        assert result is None

    def test_bcr_exactly_at_threshold(self):
        # BCR = 1_500 / 1_000 = 1.5 → exactly at lower threshold
        result = detect_backlog(self._stock(1_500, 1_000), [])
        assert result is not None
        assert result.confidence == 0.5

    def test_missing_backlog_returns_none(self):
        result = detect_backlog(self._stock(None, 1_000), [])
        assert result is None

    def test_missing_revenue_returns_none(self):
        result = detect_backlog(self._stock(2_000, None), [])
        assert result is None

    def test_zero_revenue_returns_none(self):
        result = detect_backlog(self._stock(2_000, 0), [])
        assert result is None

    def test_yoy_bonus_applied(self):
        # BCR = 2.0 → 0.7 base, YoY = 100% → +0.15 = 0.85
        result = detect_backlog(self._stock(2_000, 1_000, backlog_prev=1_000), [])
        assert result is not None
        assert result.confidence == pytest.approx(0.85, abs=0.01)

    def test_confidence_capped_at_1(self):
        # BCR = 5.0, YoY = 200% → should not exceed 1.0
        result = detect_backlog(self._stock(5_000, 1_000, backlog_prev=500), [])
        assert result is not None
        assert result.confidence <= 1.0

    def test_evidence_contains_bcr_type(self):
        result = detect_backlog(self._stock(2_000, 1_000), [])
        assert result is not None
        types = [e["source_type"] for e in result.evidence]
        assert "bcr" in types


# ── TestProfitInflect ─────────────────────────────────────────────────────────

class TestProfitInflect:
    def _stock(self, opm_ttm, opm_prev):
        return {"ticker": "TEST02", "op_margin_ttm": opm_ttm, "op_margin_prev": opm_prev}

    def test_inflection_from_sub5_base(self):
        result = detect_profit(self._stock(6.5, 3.0), [])
        assert result is not None
        assert result.confidence == 0.6  # gap 3.5pp → 2-4pp range

    def test_large_gap_higher_confidence(self):
        result = detect_profit(self._stock(10.0, 4.0), [])
        assert result is not None
        assert result.confidence == pytest.approx(0.7, abs=0.01)

    def test_high_base_no_match(self):
        # op_margin_prev >= 5% → skip
        result = detect_profit(self._stock(12.0, 6.0), [])
        assert result is None

    def test_gap_below_2pp_no_match(self):
        result = detect_profit(self._stock(4.0, 3.0), [])  # gap 1pp
        assert result is None

    def test_missing_margin_data_returns_none(self):
        assert detect_profit({"ticker": "T", "op_margin_ttm": None, "op_margin_prev": 2.0}, []) is None
        assert detect_profit({"ticker": "T", "op_margin_ttm": 5.0, "op_margin_prev": None}, []) is None

    def test_evidence_contains_opm_delta_type(self):
        result = detect_profit(self._stock(8.0, 1.0), [])
        assert result is not None
        types = [e["source_type"] for e in result.evidence]
        assert "opm_delta" in types


# ── TestBigtechPartner ────────────────────────────────────────────────────────

class TestBigtechPartner:
    def test_bigtech_callopt_high_confidence(self):
        filing = _filing("삼성전자, 레인보우로보틱스 유상증자 참여 + 콜옵션 체결")
        result = detect_bigtech({"ticker": "277810"}, [filing])
        assert result is not None
        assert result.confidence == 0.9

    def test_bigtech_equity_no_callopt_lower(self):
        # LG전자(KR bigtech investor) + equity hit => 0.80 (raised from 0.70 for KR big tech)
        filing = _filing("LG전자, 로보티즈 지분 취득 전략적 투자")
        result = detect_bigtech({"ticker": "108490"}, [filing])
        assert result is not None
        assert result.confidence == 0.80

    def test_no_bigtech_keyword_no_match(self):
        filing = _filing("일반 공급 계약 체결 완료")
        result = detect_bigtech({"ticker": "000001"}, [filing])
        assert result is None

    def test_bigtech_no_equity_no_match(self):
        # BigTech present but no equity/callopt keyword
        filing = _filing("NVIDIA와 공급 계약 체결")
        result = detect_bigtech({"ticker": "000001"}, [filing])
        assert result is None

    def test_imports_from_classifier_not_duplicate(self):
        # Verify keyword lists come from classifier.py
        from src.hundredx.keywords import BIGTECH_KEYWORDS
        from src.hundredx.categories.bigtech_partner import BIGTECH_KEYWORDS as imported
        assert imported is BIGTECH_KEYWORDS

    def test_empty_filings_no_match(self):
        result = detect_bigtech({"ticker": "000001"}, [])
        assert result is None

    def test_samsung_robotics_investment_detected(self):
        """277810 (레인보우로보틱스) type: 삼성전자 유상증자 + 콜옵션 → 0.90"""
        filing = _filing("삼성전자 레인보우로보틱스 유상증자 참여 지분 취득 및 콜옵션 계약")
        result = detect_bigtech({"ticker": "277810"}, [filing])
        assert result is not None
        assert result.confidence >= 0.90

    def test_kr_bigtech_equity_only_gets_0_80(self):
        """KR 대기업 지분 취득만으로도 0.80 (global bigtech의 0.70보다 높음)"""
        filing = _filing("현대차 로봇 스타트업 지분 취득 전략적 투자")
        result = detect_bigtech({"ticker": "TEST01"}, [filing])
        assert result is not None
        assert result.confidence == 0.80

    def test_hyperscaler_pcb_supply_detected(self):
        """이수페타시스 type: 하이퍼스케일러 대상 고다층 PCB 공급 → 탐지"""
        # sector_tag = "PCB" → in_target_sector=True; hyperscaler + bigtech keywords
        filing = _filing("Microsoft Azure 데이터센터 향 고다층 MLB PCB 공급 계약 체결")
        result = detect_bigtech({"ticker": "007660", "sector_tag": "pcb 기판 인쇄회로"}, [filing])
        assert result is not None
        assert result.confidence >= 0.70

    def test_global_bigtech_supply_with_sector_match(self):
        """NVIDIA + 공급 계약 + 반도체 섹터 → 탐지 (sector bonus)"""
        filing = _filing("NVIDIA 향 냉각 솔루션 공급 계약 체결 확정")
        result = detect_bigtech({"ticker": "TEST02", "sector_tag": "냉각 열관리"}, [filing])
        assert result is not None
        assert result.confidence >= 0.75


# ── TestPlatformMono ──────────────────────────────────────────────────────────

class TestPlatformMono:
    def test_monopoly_plus_patent_matches(self):
        filing = _filing("독점 공급자로 선정, 특허 인증 획득")
        result = detect_mono({"ticker": "000001"}, [filing])
        assert result is not None
        assert result.confidence == 0.5

    def test_monopoly_no_patent_no_match(self):
        filing = _filing("시장점유율 1위 독점")
        result = detect_mono({"ticker": "000001"}, [filing])
        assert result is None

    def test_two_monopoly_keywords_higher_confidence(self):
        filing = _filing("독점 공급, 시장점유율 1위, 특허 등록")
        result = detect_mono({"ticker": "000001"}, [filing])
        assert result is not None
        assert result.confidence == 0.8  # 2+ monopoly keywords

    def test_patent_no_monopoly_no_match(self):
        filing = _filing("신제품 특허 출원")
        result = detect_mono({"ticker": "000001"}, [filing])
        assert result is None

    def test_imports_monopoly_keywords_from_classifier(self):
        from src.hundredx.keywords import MONOPOLY_KEYWORDS
        from src.hundredx.categories.platform_mono import MONOPOLY_KEYWORDS as imported
        assert imported is MONOPOLY_KEYWORDS


# ── TestPolicyBenefit ─────────────────────────────────────────────────────────

class TestPolicyBenefit:
    def test_geo_keyword_with_defense_sector(self):
        filing = _filing("IRA 법안 국산화 수혜 기대")
        result = detect_policy({"ticker": "T", "sector_tag": "방산"}, [filing])
        assert result is not None
        assert result.confidence >= 0.7

    def test_geo_keyword_without_sector_match(self):
        filing = _filing("NATO 재무장 방산 수출 확대")
        result = detect_policy({"ticker": "T", "sector_tag": "IT서비스"}, [filing])
        assert result is not None
        assert result.confidence >= 0.5

    def test_wrong_sector_no_boost(self):
        filing = _filing("리쇼어링 공급망 재편 수혜")
        result = detect_policy({"ticker": "T", "sector_tag": "소비재"}, [filing])
        assert result is not None
        assert result.confidence >= 0.5

    def test_nuclear_sector_boosts(self):
        filing = _filing("에너지 안보 원전 르네상스 수혜")
        result = detect_policy({"ticker": "T", "sector_tag": "원전"}, [filing])
        assert result is not None
        assert result.confidence >= 0.7

    def test_no_geo_keyword_no_match(self):
        filing = _filing("일반 영업 공시")
        result = detect_policy({"ticker": "T", "sector_tag": "방산"}, [filing])
        assert result is None


# ── TestSupplyChoke ───────────────────────────────────────────────────────────

class TestSupplyChoke:
    def test_keyword_only_base_confidence(self):
        filing = _filing("변압기 공급 부족, supply shortage 심화")
        result = detect_supply({"ticker": "T"}, [filing])
        assert result is not None
        assert result.confidence == 0.5

    def test_keyword_plus_large_amount_high_confidence(self):
        # 1조원 → _extract_amount_krw returns 1_000 (after bug fix)
        filing = _filing("광섬유 병목 현상 심화, 수급 불균형", "수요 초과, 계약 금액 1조원")
        result = detect_supply({"ticker": "T"}, [filing])
        assert result is not None
        assert result.confidence >= 0.7

    def test_no_keyword_no_match(self):
        filing = _filing("일반 계약 체결 공시")
        result = detect_supply({"ticker": "T"}, [filing])
        assert result is None

    def test_imports_supply_keywords_from_classifier(self):
        from src.hundredx.keywords import SUPPLY_BOTTLENECK_KEYWORDS
        from src.hundredx.categories.supply_choke import SUPPLY_BOTTLENECK_KEYWORDS as imported
        assert imported is SUPPLY_BOTTLENECK_KEYWORDS


# ── TestClinicalPipe ──────────────────────────────────────────────────────────

class TestClinicalPipe:
    def test_keyword_in_one_filing(self):
        # Single filing with general clinical keywords: 0.70 (raised from 0.5 to pass scanner min_conf)
        filing = _filing("FDA IND 임상시험계획 승인 획득", filing_id="f1")
        result = detect_clinical({"ticker": "T"}, [filing])
        assert result is not None
        assert result.confidence == 0.70

    def test_keyword_in_both_filings_higher_confidence(self):
        # f1: general keywords (임상, 1상, IND); f2: strong keywords (기술이전, 마일스톤)
        # 2+ strong keywords => base=0.75; + license_hits w/o amount => 0.75+0.07=0.82
        f1 = _filing("임상 1상 진입 IND 제출", filing_id="f1")
        f2 = _filing("기술이전 마일스톤 달성", filing_id="f2")
        result = detect_clinical({"ticker": "T"}, [f1, f2])
        assert result is not None
        assert result.confidence == 0.82

    def test_no_biotech_keywords_no_match(self):
        filing = _filing("일반 영업 공시")
        result = detect_clinical({"ticker": "T"}, [filing])
        assert result is None

    def test_empty_filings_no_match(self):
        result = detect_clinical({"ticker": "T"}, [])
        assert result is None

    def test_only_first_two_filings_checked(self):
        # 3 filings: only first 2 are checked; 3rd should not affect result
        f1 = _filing("일반 공시", filing_id="f1")
        f2 = _filing("일반 공시", filing_id="f2")
        f3 = _filing("임상 1상 IND FDA 승인", filing_id="f3")
        result = detect_clinical({"ticker": "T"}, [f1, f2, f3])
        assert result is None  # f3 not checked

    def test_imports_biotech_keywords_from_classifier(self):
        from src.hundredx.keywords import BIOTECH_PIPELINE_KEYWORDS
        from src.hundredx.categories.clinical_pipe import BIOTECH_PIPELINE_KEYWORDS as imported
        assert imported is BIOTECH_PIPELINE_KEYWORDS

    def test_stage_transition_1_to_2_boosts_confidence(self):
        # older filing: 1상, recent: 2상 → delta=1 → confidence=0.85
        f_recent = _filing("임상 2상 진입 완료 (phase 2 initiated)", filing_id="f1")
        f_older  = _filing("임상 1상 결과 발표 주요사항보고서", filing_id="f2")
        result = detect_clinical({"ticker": "T"}, [f_recent, f_older])
        assert result is not None
        assert result.confidence == 0.85
        # Stage transition evidence should appear
        stage_ev = [e for e in result.evidence if e.get("source_type") == "stage_transition"]
        assert len(stage_ev) == 1
        assert stage_ev[0]["amount"] == 1.0

    def test_stage_transition_1_to_3_boosts_to_max(self):
        # 2-step jump (1상→3상) → confidence=0.9
        f_recent = _filing("임상 3상 진입 FDA 신청 (phase 3)", filing_id="f1")
        f_older  = _filing("임상 1상 안전성 확인 IND", filing_id="f2")
        result = detect_clinical({"ticker": "T"}, [f_recent, f_older])
        assert result is not None
        assert result.confidence == 0.9

    def test_stage_regression_no_boost(self):
        # 3상 in older, 1상 in recent → no stage transition boost
        f_recent = _filing("임상 1상 추가 코호트", filing_id="f1")
        f_older  = _filing("임상 3상 완료 NDA 제출", filing_id="f2")
        result = detect_clinical({"ticker": "T"}, [f_recent, f_older])
        assert result is not None
        # Both have general keywords, no strong keywords → base=0.72 (raised from 0.70)
        assert result.confidence == 0.72

    def test_glp1_strong_keyword_boosts_confidence(self):
        """펩트론 type: GLP-1 펩타이드 신약 → strong keyword → 0.70+"""
        filing = _filing("GLP-1 기반 펩타이드 신약 후보물질 임상 1상 진입")
        result = detect_clinical({"ticker": "087010"}, [filing])
        assert result is not None
        # GLP-1 is a strong keyword → base >= 0.72
        assert result.confidence >= 0.70

    def test_license_out_with_amount_high_confidence(self):
        """기술이전 + 마일스톤 + 대형 계약 → 높은 confidence"""
        filing = _filing("Merck에 기술이전, 마일스톤 1500억원 규모 라이선스 계약 체결")
        result = detect_clinical({"ticker": "T"}, [filing])
        assert result is not None
        # license_hits + amount >= 100bn → big bonus
        assert result.confidence >= 0.82

    def test_ophthalmic_keywords_detected(self):
        """삼천당제약 type: 안과 점안제 → 탐지"""
        filing = _filing("점안제 황반변성 치료제 임상 3상 완료 품목허가 신청")
        result = detect_clinical({"ticker": "000250"}, [filing])
        assert result is not None
        assert result.confidence >= 0.70

    def test_single_strong_keyword_passes_scanner_threshold(self):
        """단일 강력 키워드(GLP-1/기술이전 등)가 scanner 최소 신뢰도(0.70) 통과"""
        filing = _filing("바이오시밀러 허가신청 FDA 제출 완료")
        result = detect_clinical({"ticker": "T"}, [filing])
        assert result is not None
        assert result.confidence >= 0.70  # Must pass scanner MIN_CONFIDENCE=0.70
