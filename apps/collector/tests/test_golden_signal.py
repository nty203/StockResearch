"""Tests for golden_signal.py — 2+ golden-type triggers → golden=True."""
import pytest
from unittest.mock import MagicMock, patch

from src.triggers.golden_signal import detect_golden, GOLDEN_TRIGGER_TYPES, GOLDEN_THRESHOLD
from src.triggers.classifier import TriggerResult


def _make_trigger(trigger_type: str, confidence: float = 0.7) -> TriggerResult:
    return TriggerResult(
        trigger_type=trigger_type,
        confidence=confidence,
        matched_keywords=["test"],
        summary=f"Test: {trigger_type}",
    )


class TestDetectGolden:
    def test_two_golden_types_is_golden(self):
        filing = {
            "id": "f1",
            "ticker": "298040",
            "headline": "한미반도체 NVIDIA 600억 TC본더 수주, CAPEX 증설 착공",
            "raw_text": "한미반도체 NVIDIA 600억원 TC본더 수주 계약 체결. CAPEX 공장 증설 착공.",
        }
        with patch("src.triggers.golden_signal.classify_filing") as mock_classify:
            mock_classify.return_value = [
                _make_trigger("단일_수주", 0.8),
                _make_trigger("CAPEX_증설", 0.7),
                _make_trigger("실적_서프라이즈", 0.5),
            ]
            golden, results = detect_golden(filing)

        assert golden is True
        assert len(results) == 3

    def test_one_golden_type_not_golden(self):
        filing = {"id": "f2", "ticker": "000001", "headline": "수주", "raw_text": "수주"}
        with patch("src.triggers.golden_signal.classify_filing") as mock_classify:
            mock_classify.return_value = [
                _make_trigger("단일_수주", 0.8),   # only 1 golden type
                _make_trigger("실적_서프라이즈", 0.9),  # not golden type
            ]
            golden, _ = detect_golden(filing)

        assert golden is False

    def test_zero_triggers_not_golden(self):
        filing = {"id": "f3", "ticker": "000002", "headline": "", "raw_text": ""}
        with patch("src.triggers.golden_signal.classify_filing") as mock_classify:
            mock_classify.return_value = []
            golden, _ = detect_golden(filing)

        assert golden is False

    def test_low_confidence_triggers_not_golden(self):
        """Golden types below confidence 0.4 should not count."""
        filing = {"id": "f4", "ticker": "000003", "headline": "test", "raw_text": "test"}
        with patch("src.triggers.golden_signal.classify_filing") as mock_classify:
            mock_classify.return_value = [
                _make_trigger("단일_수주", 0.2),    # below 0.4
                _make_trigger("CAPEX_증설", 0.3),   # below 0.4
                _make_trigger("빅테크_파트너", 0.1), # below 0.4
            ]
            golden, _ = detect_golden(filing)

        assert golden is False

    def test_three_golden_types_is_golden(self):
        filing = {"id": "f5", "ticker": "000004", "headline": "test", "raw_text": "test"}
        with patch("src.triggers.golden_signal.classify_filing") as mock_classify:
            mock_classify.return_value = [
                _make_trigger("단일_수주", 0.9),
                _make_trigger("CAPEX_증설", 0.8),
                _make_trigger("빅테크_파트너", 0.7),
            ]
            golden, _ = detect_golden(filing)

        assert golden is True

    def test_returns_all_results_regardless_of_golden(self):
        filing = {"id": "f6", "ticker": "000005", "headline": "", "raw_text": ""}
        all_triggers = [
            _make_trigger("단일_수주", 0.8),
            _make_trigger("지정학_수혜", 0.6),
        ]
        with patch("src.triggers.golden_signal.classify_filing") as mock_classify:
            mock_classify.return_value = all_triggers
            _, results = detect_golden(filing)

        assert len(results) == 2

    def test_global_mega_is_golden_type(self):
        """글로벌_메가계약 should count as a golden type."""
        assert "글로벌_메가계약" in GOLDEN_TRIGGER_TYPES

    def test_bigtech_partner_is_golden_type(self):
        assert "빅테크_파트너" in GOLDEN_TRIGGER_TYPES

    def test_golden_threshold_is_two(self):
        assert GOLDEN_THRESHOLD == 2

    def test_non_golden_types_do_not_count(self):
        """지정학_수혜, 실적_서프라이즈 alone cannot make golden=True."""
        filing = {"id": "f7", "ticker": "000006", "headline": "", "raw_text": ""}
        with patch("src.triggers.golden_signal.classify_filing") as mock_classify:
            mock_classify.return_value = [
                _make_trigger("지정학_수혜", 0.9),
                _make_trigger("실적_서프라이즈", 0.9),
                _make_trigger("규제_해소", 0.9),
            ]
            golden, _ = detect_golden(filing)

        assert golden is False
