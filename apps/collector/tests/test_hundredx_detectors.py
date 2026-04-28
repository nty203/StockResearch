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
        assert result.confidence == 0.8  # gap 6pp → >5pp range

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
        filing = _filing("LG전자, 로보티즈 지분 취득 전략적 투자")
        result = detect_bigtech({"ticker": "108490"}, [filing])
        assert result is not None
        assert result.confidence == 0.7

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
        from src.triggers.classifier import BIGTECH_KEYWORDS
        from src.hundredx.categories.bigtech_partner import BIGTECH_KEYWORDS as imported
        assert imported is BIGTECH_KEYWORDS

    def test_empty_filings_no_match(self):
        result = detect_bigtech({"ticker": "000001"}, [])
        assert result is None


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
        from src.triggers.classifier import MONOPOLY_KEYWORDS
        from src.hundredx.categories.platform_mono import MONOPOLY_KEYWORDS as imported
        assert imported is MONOPOLY_KEYWORDS


# ── TestPolicyBenefit ─────────────────────────────────────────────────────────

class TestPolicyBenefit:
    def test_geo_keyword_with_defense_sector(self):
        filing = _filing("IRA 법안 국산화 수혜 기대")
        result = detect_policy({"ticker": "T", "sector_tag": "방산"}, [filing])
        assert result is not None
        assert result.confidence == 0.7

    def test_geo_keyword_without_sector_match(self):
        filing = _filing("NATO 재무장 방산 수출 확대")
        result = detect_policy({"ticker": "T", "sector_tag": "IT서비스"}, [filing])
        assert result is not None
        assert result.confidence == 0.5

    def test_wrong_sector_no_boost(self):
        filing = _filing("리쇼어링 공급망 재편 수혜")
        result = detect_policy({"ticker": "T", "sector_tag": "소비재"}, [filing])
        assert result is not None
        assert result.confidence == 0.5  # no sector boost

    def test_nuclear_sector_boosts(self):
        filing = _filing("에너지 안보 원전 르네상스 수혜")
        result = detect_policy({"ticker": "T", "sector_tag": "원전"}, [filing])
        assert result is not None
        assert result.confidence == 0.7

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
        assert result.confidence == 0.7

    def test_no_keyword_no_match(self):
        filing = _filing("일반 계약 체결 공시")
        result = detect_supply({"ticker": "T"}, [filing])
        assert result is None

    def test_imports_supply_keywords_from_classifier(self):
        from src.triggers.classifier import SUPPLY_BOTTLENECK_KEYWORDS
        from src.hundredx.categories.supply_choke import SUPPLY_BOTTLENECK_KEYWORDS as imported
        assert imported is SUPPLY_BOTTLENECK_KEYWORDS


# ── TestClinicalPipe ──────────────────────────────────────────────────────────

class TestClinicalPipe:
    def test_keyword_in_one_filing(self):
        filing = _filing("FDA IND 임상시험계획 승인 획득", filing_id="f1")
        result = detect_clinical({"ticker": "T"}, [filing])
        assert result is not None
        assert result.confidence == 0.5

    def test_keyword_in_both_filings_higher_confidence(self):
        f1 = _filing("임상 1상 진입 IND 제출", filing_id="f1")
        f2 = _filing("기술이전 마일스톤 달성", filing_id="f2")
        result = detect_clinical({"ticker": "T"}, [f1, f2])
        assert result is not None
        assert result.confidence == 0.7

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
        from src.triggers.classifier import BIOTECH_PIPELINE_KEYWORDS
        from src.hundredx.categories.clinical_pipe import BIOTECH_PIPELINE_KEYWORDS as imported
        assert imported is BIOTECH_PIPELINE_KEYWORDS
