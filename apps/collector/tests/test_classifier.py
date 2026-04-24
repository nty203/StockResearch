"""Tests for trigger classifier — 15 trigger types."""
import pytest
from src.triggers.classifier import classify, classify_filing, TriggerResult


class TestClassify:
    def test_sk_hynix_tc_bonder_is_single_order(self):
        text = "SK하이닉스, NVIDIA에 600억원 규모 TC본더 수주 계약 체결"
        results = classify(text)
        types = [r.trigger_type for r in results]
        assert "단일_수주" in types

    def test_sk_hynix_confidence_high(self):
        text = "SK하이닉스, NVIDIA에 600억원 규모 TC본더 수주 계약 체결"
        results = classify(text)
        single_order = next((r for r in results if r.trigger_type == "단일_수주"), None)
        assert single_order is not None
        assert single_order.confidence >= 0.4

    def test_capex_expansion(self):
        text = "삼성전자, 평택 반도체 공장 2조원 증설 착공"
        results = classify(text)
        types = [r.trigger_type for r in results]
        assert "CAPEX_증설" in types

    def test_bigtech_partner(self):
        text = "한미반도체, Microsoft와 AI 메모리 전략적 파트너십 체결 MOU"
        results = classify(text)
        types = [r.trigger_type for r in results]
        assert "빅테크_파트너" in types

    def test_global_mega_contract(self):
        text = "한화에어로스페이스, 폴란드 NATO 방산 수출 계약 2조원 규모"
        results = classify(text)
        types = [r.trigger_type for r in results]
        assert "글로벌_메가계약" in types

    def test_monopoly_signal(self):
        text = "에코프로비엠, 배터리 양극재 시장 독점 지위 확보, 시장점유율 45%"
        results = classify(text)
        types = [r.trigger_type for r in results]
        assert "시장_독점" in types

    def test_tech_breakthrough(self):
        text = "POSCO홀딩스, 리튬 추출 기술 세계 최초 특허 양산 성공"
        results = classify(text)
        types = [r.trigger_type for r in results]
        assert "기술_돌파" in types

    def test_insider_buy(self):
        text = "대주주, 자사주 매입 500억원 규모 공시"
        results = classify(text)
        types = [r.trigger_type for r in results]
        assert "내부자_매수" in types

    def test_regulatory_approval(self):
        text = "셀트리온, 유럽 EMA 바이오시밀러 규제 승인 허가 획득"
        results = classify(text)
        types = [r.trigger_type for r in results]
        assert "규제_해소" in types

    def test_geopolitical(self):
        text = "미국 CHIPS Act 보조금, 국산화 반도체 리쇼어링 공급망 재편 수혜"
        results = classify(text)
        types = [r.trigger_type for r in results]
        assert "지정학_수혜" in types

    def test_earnings_surprise(self):
        text = "어닝 서프라이즈, 컨센서스 상회 예상치 초과 실적 호조"
        results = classify(text)
        types = [r.trigger_type for r in results]
        assert "실적_서프라이즈" in types

    def test_empty_text_returns_empty(self):
        results = classify("")
        assert results == []

    def test_irrelevant_text_no_high_confidence(self):
        text = "오늘 날씨가 맑고 기온이 적당합니다."
        results = classify(text)
        # No trigger types should match with high confidence
        assert all(r.confidence < 0.5 for r in results)

    def test_results_sorted_by_confidence(self):
        text = "SK하이닉스, NVIDIA에 600억원 규모 수주 계약, 증설 착공 CAPEX 투자"
        results = classify(text)
        if len(results) > 1:
            for i in range(len(results) - 1):
                assert results[i].confidence >= results[i + 1].confidence

    def test_amount_parsed(self):
        text = "반도체 장비 600억원 수주 계약 체결 NVIDIA"
        results = classify(text)
        order = next((r for r in results if r.trigger_type == "단일_수주"), None)
        if order:
            assert order.parsed_amount is not None
            assert order.parsed_amount > 0

    def test_trigger_result_has_keywords(self):
        text = "SK하이닉스, NVIDIA TC본더 수주 계약"
        results = classify(text)
        for r in results:
            assert isinstance(r.matched_keywords, list)
            assert isinstance(r.summary, str)

    def test_result_type(self):
        text = "NVDA AWS 수주 계약 체결"
        results = classify(text)
        for r in results:
            assert isinstance(r, TriggerResult)


class TestClassifyFiling:
    def test_filing_dict_input(self):
        filing = {
            "id": "123",
            "ticker": "298040",
            "headline": "한미반도체 NVIDIA 600억 TC본더 수주",
            "raw_text": "한미반도체가 NVIDIA에 TC본더 600억원 수주 계약을 체결했습니다.",
        }
        results = classify_filing(filing)
        assert isinstance(results, list)
        types = [r.trigger_type for r in results]
        assert "단일_수주" in types

    def test_empty_filing(self):
        filing = {"id": "empty", "ticker": "000000", "headline": "", "raw_text": ""}
        results = classify_filing(filing)
        assert results == []
