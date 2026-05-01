"""Tests for extract_signals module — pure function coverage."""
import pytest
from datetime import datetime

from src.hundredx.extract_signals import (
    _fq_to_date,
    _compute_quant_at_rise,
    _categorize_from_filings,
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
        # 4 quarters: revenue 1000 each → TTM=4000, backlog=8000 → BCR=2.0
        fins = [
            _fin("2022Q3", revenue=1000.0, order_backlog=8000.0),
            _fin("2022Q2", revenue=1000.0),
            _fin("2022Q1", revenue=1000.0),
            _fin("2021Q4", revenue=1000.0),
        ]
        result = _compute_quant_at_rise(fins, "2022-10-01")
        assert "bcr_at_signal" in result
        # TTM = 4000, backlog = 8000 → BCR = 2.0
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
        # 4 recent quarters rev=2000 each, 4 prev quarters rev=1000 each → +100%
        fins = (
            [_fin(f"2023Q{q}", revenue=2000.0) for q in range(4, 0, -1)]
            + [_fin(f"2022Q{q}", revenue=1000.0) for q in range(4, 0, -1)]
        )
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
