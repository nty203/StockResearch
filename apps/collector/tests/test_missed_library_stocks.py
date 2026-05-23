"""Simulation tests for previously-missed library stocks.

Tests that our enhanced detectors can catch the known 100x stocks
if they were to file similar disclosures TODAY.

Library stocks with 0% detection being tested:
  277810 (레인보우로보틱스) - 빅테크_파트너, 20x rise
  087010 (펩트론) - 임상_파이프라인, 41x rise
  000250 (삼천당제약) - 임상_파이프라인, ophthalmic
  007660 (이수페타시스) - 빅테크_파트너, 54x rise
  001570 (에코프로비엠/이차전지_소재 type)
"""
import pytest

# ── imports ─────────────────────────────────────────────────────────────────────
from src.hundredx.categories.bigtech_partner import detect as detect_bigtech
from src.hundredx.categories.clinical_pipe import detect as detect_clinical
from src.hundredx.categories.supply_choke import detect as detect_supply
from src.hundredx.categories.policy_benefit import detect as detect_policy


def _filing(headline: str, raw_text: str = "", filing_id: str = "test_filing"):
    return {
        "id": filing_id,
        "headline": headline,
        "raw_text": raw_text,
        "filed_at": "2026-05-23",
    }


SCANNER_MIN_CONF = 0.70  # from scanner.py MIN_CONFIDENCE


# ── 277810 레인보우로보틱스 (빅테크_파트너, 삼성전자 투자) ─────────────────────────

class TestRainbowRobotics:
    """277810 레인보우로보틱스 — 삼성전자 유상증자 참여 + 콜옵션 → 20x rise."""

    def test_samsung_equity_stake_detected(self):
        """삼성전자가 지분 취득 + 콜옵션 → 최고 신뢰도"""
        filing = _filing(
            "삼성전자, 레인보우로보틱스 유상증자 참여 지분 취득 및 콜옵션 행사 계약",
            raw_text="삼성전자가 레인보우로보틱스에 유상증자 참여를 통해 지분을 취득하였으며, "
                     "추가적으로 콜옵션 조건부 최대주주 전환 계약을 체결하였습니다."
        )
        stock = {"ticker": "277810", "sector_tag": "로봇 자동화 제조"}
        result = detect_bigtech(stock, [filing])
        assert result is not None, "삼성전자 지분투자 + 콜옵션 → 탐지되어야 함"
        assert result.confidence >= SCANNER_MIN_CONF, f"신뢰도 {result.confidence:.2f} < {SCANNER_MIN_CONF}"
        assert result.confidence == 0.90, "equity + callopt = 0.90"

    def test_samsung_equity_without_callopt_detected(self):
        """삼성전자 단순 지분 취득만으로도 탐지 (KR investor 프리미엄 0.80)"""
        filing = _filing(
            "삼성전자 레인보우로보틱스 지분 취득 전략적 투자",
            raw_text="삼성전자가 레인보우로보틱스 지분을 취득하여 전략적 투자를 진행하였습니다."
        )
        stock = {"ticker": "277810", "sector_tag": "로봇"}
        result = detect_bigtech(stock, [filing])
        assert result is not None, "삼성전자 지분 취득 → 탐지되어야 함"
        assert result.confidence >= SCANNER_MIN_CONF, f"신뢰도 {result.confidence:.2f} < {SCANNER_MIN_CONF}"

    def test_robot_sector_supply_contract_detected(self):
        """삼성전자와 로봇 공급 계약 체결 → 로봇 섹터 + 공급 키워드"""
        filing = _filing(
            "삼성전자 공장 자동화 로봇 공급 계약 체결",
            raw_text="삼성전자와 협동로봇 및 자동화 솔루션 공급 계약을 체결하였습니다."
        )
        stock = {"ticker": "277810", "sector_tag": "로봇 협동로봇 자동화"}
        result = detect_bigtech(stock, [filing])
        assert result is not None, "삼성전자 로봇 공급 계약 → 탐지되어야 함"
        assert result.confidence >= SCANNER_MIN_CONF


# ── 087010 펩트론 (임상_파이프라인, GLP-1 비만치료제, 41x rise) ──────────────────

class TestPeptron:
    """087010 펩트론 — GLP-1 기반 펩타이드 비만치료제 임상 → 41x rise."""

    def test_glp1_clinical_trial_detected(self):
        """GLP-1 펩타이드 임상 1상 → 강력 키워드 조합"""
        filing = _filing(
            "GLP-1 기반 비만 치료 펩타이드 신약 임상 1상 진입 IND 승인",
            raw_text="GLP-1 수용체 작용제 기반 장기지속형 펩타이드 신약의 임상시험계획(IND) 승인을 "
                     "받았습니다. 비만 치료를 위한 임상 1상 환자 등록을 시작합니다."
        )
        stock = {"ticker": "087010", "sector_tag": "제약 바이오"}
        result = detect_clinical(stock, [filing])
        assert result is not None, "GLP-1 임상 1상 → 탐지되어야 함"
        assert result.confidence >= SCANNER_MIN_CONF, f"신뢰도 {result.confidence:.2f} < {SCANNER_MIN_CONF}"

    def test_glp1_licensure_detected(self):
        """GLP-1 기술이전 + 마일스톤 → 높은 신뢰도"""
        f1 = _filing(
            "GLP-1 신약 후보물질 글로벌 제약사에 기술이전 마일스톤 1000억 규모",
            raw_text="GLP-1 기반 비만치료제의 글로벌 기술이전 계약을 체결하였습니다. "
                     "총 마일스톤 규모는 1000억원 이상이며, 선급금 200억원을 수령하였습니다.",
            filing_id="f1"
        )
        f2 = _filing(
            "GLP-1 펩타이드 임상 2상 결과 발표",
            raw_text="임상 2상에서 우수한 체중 감소 효과를 확인하였습니다.",
            filing_id="f2"
        )
        stock = {"ticker": "087010", "sector_tag": "제약"}
        result = detect_clinical(stock, [f1, f2])
        assert result is not None, "GLP-1 기술이전 → 탐지되어야 함"
        assert result.confidence >= 0.80, f"기술이전 1000억 → 신뢰도 {result.confidence:.2f} >= 0.80 기대"

    def test_stage_transition_2_to_3_detected(self):
        """임상 2상→3상 전이 → 0.85 confidence"""
        f_recent = _filing("GLP-1 펩타이드 임상 3상 진입 FDA phase 3", filing_id="f1")
        f_older = _filing("GLP-1 임상 2상 결과 우수 안전성 확인", filing_id="f2")
        stock = {"ticker": "087010"}
        result = detect_clinical(stock, [f_recent, f_older])
        assert result is not None
        assert result.confidence == 0.85


# ── 000250 삼천당제약 (임상_파이프라인, 안과/점안제) ────────────────────────────────

class TestSamchundang:
    """000250 삼천당제약 — 안과 점안제 바이오시밀러 임상/허가."""

    def test_ophthalmic_clinical_detected(self):
        """점안제 황반변성 임상 3상 허가 신청"""
        filing = _filing(
            "황반변성 치료제 점안제 임상 3상 완료 식약처 품목허가 신청",
            raw_text="항체의약품 라니비주맙 바이오시밀러 점안제의 임상 3상을 성공적으로 완료하고 "
                     "식약처에 품목허가(NDA)를 신청하였습니다."
        )
        stock = {"ticker": "000250", "sector_tag": "제약 안과"}
        result = detect_clinical(stock, [filing])
        assert result is not None, "안과 임상 3상 허가신청 → 탐지되어야 함"
        assert result.confidence >= SCANNER_MIN_CONF

    def test_biosimilar_license_detected(self):
        """바이오시밀러 기술이전 + 마일스톤"""
        filing = _filing(
            "안과 바이오시밀러 기술이전 계약 체결 마일스톤 500억",
            raw_text="라니비주맙 바이오시밀러의 기술이전 계약을 체결하였으며 "
                     "마일스톤을 포함한 총 계약 규모는 500억원입니다."
        )
        stock = {"ticker": "000250"}
        result = detect_clinical(stock, [filing])
        assert result is not None, "바이오시밀러 기술이전 → 탐지되어야 함"
        assert result.confidence >= SCANNER_MIN_CONF


# ── 007660 이수페타시스 (빅테크_파트너, 하이퍼스케일러 PCB 공급, 54x rise) ─────────

class TestIsupetasis:
    """007660 이수페타시스 — Microsoft/AWS 데이터센터용 고다층 PCB 공급 → 54x rise."""

    def test_hyperscaler_pcb_supply_detected(self):
        """Microsoft 데이터센터용 고다층 MLB PCB 공급 계약"""
        filing = _filing(
            "Microsoft Azure 하이퍼스케일 데이터센터 AI 서버용 고다층 MLB PCB 공급 계약",
            raw_text="Microsoft Azure 데이터센터에 납품하는 AI GPU 서버용 고다층 MLB 기판 "
                     "공급 계약을 체결하였습니다. 장기 공급 협력 파트너로 선정되었습니다."
        )
        stock = {"ticker": "007660", "sector_tag": "pcb 기판 인쇄회로"}
        result = detect_bigtech(stock, [filing])
        assert result is not None, "하이퍼스케일러 PCB 공급 → 탐지되어야 함"
        assert result.confidence >= SCANNER_MIN_CONF

    def test_aws_server_supply_detected(self):
        """Amazon AWS 서버용 PCB 납품"""
        filing = _filing(
            "Amazon AWS 데이터센터 서버용 기판 납품 계약 체결",
            raw_text="Amazon AWS에 데이터센터 서버 기판을 납품하는 공급 계약을 체결하였습니다."
        )
        stock = {"ticker": "007660", "sector_tag": "pcb 고다층"}
        result = detect_bigtech(stock, [filing])
        assert result is not None, "Amazon AWS PCB 납품 → 탐지되어야 함"
        assert result.confidence >= SCANNER_MIN_CONF


# ── 이차전지_소재 (에코프로비엠 type, 공급_병목/정책_수혜) ──────────────────────────

class TestBatteryMaterials:
    """배터리 소재 기업 (양극재, 전구체 등) — 공급_병목 또는 정책_수혜로 탐지."""

    def test_cathode_supply_bottleneck(self):
        """양극재 공급 부족 → 공급_병목 탐지"""
        filing = _filing(
            "양극재 공급 부족 심화, EV 배터리 수요 초과로 수급 불균형",
            raw_text="전기차(EV) 배터리 수요 급증으로 양극재 공급 부족이 심화되고 있습니다. "
                     "이차전지 소재 공급 타이트 현상이 지속되고 있습니다."
        )
        stock = {"ticker": "TEST01", "sector_tag": "양극재 이차전지 소재"}
        result = detect_supply(stock, [filing])
        assert result is not None, "양극재 공급 부족 → 공급_병목 탐지되어야 함"
        assert result.confidence >= SCANNER_MIN_CONF

    def test_ira_battery_policy_benefit(self):
        """IRA 배터리 보조금 수혜 → 정책_수혜 탐지"""
        filing = _filing(
            "IRA Inflation Reduction Act 배터리 보조금 수혜, K-배터리 소재 국산화",
            raw_text="미국 인플레이션 감축법(IRA)의 배터리 보조금 수혜 대상으로 선정되어 "
                     "K-배터리 생태계 육성 정책의 직접적인 수혜를 받을 것으로 기대됩니다."
        )
        stock = {"ticker": "TEST01", "sector_tag": "이차전지 양극재"}
        result = detect_policy(stock, [filing])
        assert result is not None, "IRA 배터리 보조금 → 정책_수혜 탐지되어야 함"
        assert result.confidence >= SCANNER_MIN_CONF

    def test_lithium_supply_shortage(self):
        """리튬 공급 부족 + 배터리 소재 섹터"""
        filing = _filing(
            "리튬 공급 부족 지속, 수산화리튬 공급 타이트 전고체 배터리 소재 수요",
            raw_text="리튬 부족 현상과 수산화리튬 공급 타이트가 지속되고 있습니다."
        )
        stock = {"ticker": "TEST02", "sector_tag": "배터리 소재 전구체"}
        result = detect_supply(stock, [filing])
        assert result is not None, "리튬 공급 부족 → 공급_병목 탐지되어야 함"
        assert result.confidence >= SCANNER_MIN_CONF
