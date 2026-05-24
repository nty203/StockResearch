"""Tests for extract_signals module — pure function coverage."""
import pytest
from datetime import datetime

from src.hundredx.extract_signals import (
    _fq_to_date,
    _compute_quant_at_rise,
    _categorize_from_filings,
    _categorize_from_texts,
    _build_news_special,
    _build_volume_special,
    _max_filing_amount,
)


class TestFqToDate:
    def test_q1_maps_to_march(self):
        d = _fq_to_date("2022Q1")
        assert d == datetime(2022, 3, 28)

    def test_q2_maps_to_june(self):
        d = _fq_to_date("2022Q2")
        assert d == datetime(2022, 6, 28)

    def test_q3_maps_to_september(self):
        d = _fq_to_date("2022Q3")
        assert d == datetime(2022, 9, 28)

    def test_q4_maps_to_december(self):
        d = _fq_to_date("2022Q4")
        assert d == datetime(2022, 12, 28)

    def test_invalid_returns_none(self):
        assert _fq_to_date("bad") is None
        assert _fq_to_date("") is None
        assert _fq_to_date("2022Q5") is None  # month 15 → ValueError


def _fin(fq: str, revenue: float = 1000.0, op_margin: float = 5.0,
         order_backlog: float | None = None) -> dict:
    return {"fq": fq, "revenue": revenue, "op_margin": op_margin,
            "order_backlog": order_backlog, "op_income": None,
            "roe": None, "roic": None, "fcf": None, "debt_ratio": None}


class TestComputeQuantAtRise:
    def test_bcr_computed_from_backlog_and_revenue(self):
        # DART cumulative: Q1=1k, Q2=2k(6mo), Q3=3k(9mo), Q4=4k(annual).
        # TTM at 2022Q3 = Q4_2021 + Q3_2022 − Q3_2021 = 4000 + 3000 − 3000 = 4000.
        # backlog=8000 → BCR=2.0
        fins = [
            _fin("2022Q3", revenue=3000.0, order_backlog=8000.0),
            _fin("2022Q2", revenue=2000.0),
            _fin("2022Q1", revenue=1000.0),
            _fin("2021Q4", revenue=4000.0),
            _fin("2021Q3", revenue=3000.0),
        ]
        result = _compute_quant_at_rise(fins, "2022-10-01")
        assert "bcr_at_signal" in result
        assert result["bcr_at_signal"] == pytest.approx(2.0, abs=0.01)

    def test_opm_delta_computed(self):
        fins = [
            _fin("2022Q3", op_margin=8.0),
            _fin("2022Q2", op_margin=3.0),
        ]
        result = _compute_quant_at_rise(fins, "2022-10-01")
        assert result.get("opm_at_signal") == pytest.approx(8.0)
        assert result.get("opm_prev") == pytest.approx(3.0)
        assert result.get("opm_delta_at_signal") == pytest.approx(5.0)

    def test_no_quarters_before_rise_returns_empty(self):
        # All quarters are after rise_start_date
        fins = [_fin("2023Q1", revenue=1000.0)]
        result = _compute_quant_at_rise(fins, "2022-10-01")
        # 2023Q1 = March 2023 > October 2022 → no relevant quarters
        assert result == {}

    def test_empty_financials_returns_empty(self):
        result = _compute_quant_at_rise([], "2022-10-01")
        assert result == {}

    def test_revenue_growth_yoy_with_8_quarters(self):
        # DART cumulative — 2023 annual=8000, 2022 annual=4000 → growth +100%.
        # Sequence (desc by fq): 2023Q4(8k), Q3(6k), Q2(4k), Q1(2k), 2022Q4(4k), Q3(3k), Q2(2k), Q1(1k)
        fins = [
            _fin("2023Q4", revenue=8000.0),
            _fin("2023Q3", revenue=6000.0),
            _fin("2023Q2", revenue=4000.0),
            _fin("2023Q1", revenue=2000.0),
            _fin("2022Q4", revenue=4000.0),
            _fin("2022Q3", revenue=3000.0),
            _fin("2022Q2", revenue=2000.0),
            _fin("2022Q1", revenue=1000.0),
        ]
        result = _compute_quant_at_rise(fins, "2024-01-01")
        assert "revenue_growth_yoy" in result
        assert result["revenue_growth_yoy"] == pytest.approx(100.0, abs=1.0)


def _filing(headline: str = "", raw_text: str = "",
            parsed_amount: float | None = None) -> dict:
    return {"headline": headline, "raw_text": raw_text,
            "parsed_amount": parsed_amount, "filed_at": "2022-01-01"}


class TestCategorizeFromFilings:
    def test_backlog_keywords_win(self):
        filings = [_filing(raw_text="수주잔고 급증 K-9 자주포 수출 계약 조원 규모 방산")]
        cat, keywords, count = _categorize_from_filings(filings)
        assert cat == "수주잔고_선행"
        assert count > 0

    def test_biotech_keywords_win(self):
        filings = [_filing(raw_text="임상 2상 완료 FDA 승인 신청 바이오 의약품 파이프라인")]
        cat, keywords, count = _categorize_from_filings(filings)
        assert cat == "임상_파이프라인"
        assert count > 0

    def test_empty_filings_returns_미분류(self):
        cat, keywords, count = _categorize_from_filings([])
        assert cat == "미분류"
        assert keywords == []
        assert count == 0

    def test_no_keyword_match_returns_미분류(self):
        filings = [_filing(raw_text="일반적인 공시 내용입니다")]
        cat, _, count = _categorize_from_filings(filings)
        assert cat == "미분류"
        assert count == 0

    def test_geopolitical_keywords_detected(self):
        # "IRA" and "supply chain" are in GEOPOLITICAL_KEYWORDS → 정책_수혜 fires
        filings = [_filing(raw_text="IRA 수혜 supply chain 재편 국산화 추진 CHIPS Act 통과")]
        cat, keywords, count = _categorize_from_filings(filings)
        assert count > 0
        # Category should be 정책_수혜 since GEOPOLITICAL_KEYWORDS matches


class TestNewsAndVolumeSpecial:
    def test_categorize_from_texts_detects_macro_news(self):
        cat, keywords, count = _categorize_from_texts([
            "IRA 수혜와 supply chain 재편으로 국산화 수요 확대",
            "AI 데이터센터 전력 부족과 전력망 투자 증가",
        ])
        assert count > 0
        assert cat in ("정책_수혜", "전력_인프라")
        assert keywords

    def test_build_news_special_summarizes_hits(self):
        news = [
            {
                "title": "IRA 수혜 기대",
                "summary": "supply chain 재편과 국산화 수요 증가",
            }
        ]
        result = _build_news_special(news)
        assert result["news_macro_hits"] > 0
        assert result["news_count"] == 1
        assert result["news_keywords"]

    def test_build_volume_special_detects_spike(self):
        prices = [
            {"date": f"2022-01-{day:02d}", "volume": 1000}
            for day in range(1, 29)
        ] + [
            {"date": f"2022-02-{day:02d}", "volume": 1000}
            for day in range(1, 23)
        ] + [
            {"date": "2022-02-23", "volume": 12000}
        ]
        result = _build_volume_special(prices)
        assert result["max_volume_spike_ratio"] == pytest.approx(12.0)
        assert result["volume_spike_date"] == "2022-02-23"
        assert result["volume_spike_required"] is True

    def test_build_volume_special_ignores_small_moves(self):
        prices = [
            {"date": f"2022-01-{day:02d}", "volume": 1000}
            for day in range(1, 29)
        ] + [
            {"date": f"2022-02-{day:02d}", "volume": 1200}
            for day in range(1, 23)
        ]
        assert _build_volume_special(prices) == {}


class TestMaxFilingAmount:
    def test_returns_largest_amount(self):
        filings = [
            _filing(parsed_amount=500.0),
            _filing(parsed_amount=1200.0),
            _filing(parsed_amount=300.0),
        ]
        assert _max_filing_amount(filings) == 1200.0

    def test_none_when_no_amounts(self):
        filings = [_filing(), _filing()]
        assert _max_filing_amount(filings) is None

    def test_skips_none_amounts(self):
        filings = [_filing(parsed_amount=None), _filing(parsed_amount=800.0)]
        assert _max_filing_amount(filings) == 800.0

    def test_empty_filings_returns_none(self):
        assert _max_filing_amount([]) is None
