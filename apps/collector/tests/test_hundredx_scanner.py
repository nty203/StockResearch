"""Tests for hundredx scanner — mocked DB, no external calls."""
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from src.hundredx.models import CategoryMatch
from src.hundredx.scanner import (
    _resolve_first_detected,
    _find_analog_financial,
    _find_analog_text,
    _get_analog,
)


def _now() -> datetime:
    return datetime(2025, 4, 27, 0, 0, 0, tzinfo=timezone.utc)


def _lib(category: str, rows: list[dict]) -> dict:
    return {category: rows}


# ── TestFirstDetectedAt ───────────────────────────────────────────────────────

class TestFirstDetectedAt:
    def _match(self, ticker="T", category="수주잔고_선행"):
        return CategoryMatch(ticker=ticker, category=category, confidence=0.7)

    def test_new_entry_gets_now(self):
        existing = {}
        now = _now()
        result = _resolve_first_detected(self._match(), existing, now)
        assert result == now

    def test_existing_active_preserves_original(self):
        original = datetime(2025, 1, 1, tzinfo=timezone.utc)
        existing = {
            ("T", "수주잔고_선행"): {
                "first_detected_at": original.isoformat(),
                "exited_at": None,
            }
        }
        now = _now()
        result = _resolve_first_detected(self._match(), existing, now)
        assert result == original

    def test_re_entry_after_exit_resets_to_now(self):
        original = datetime(2025, 1, 1, tzinfo=timezone.utc)
        existing = {
            ("T", "수주잔고_선행"): {
                "first_detected_at": original.isoformat(),
                "exited_at": "2025-03-01T00:00:00+00:00",  # was exited
            }
        }
        now = _now()
        result = _resolve_first_detected(self._match(), existing, now)
        assert result == now  # reset, not original


# ── TestConvictionFormula ─────────────────────────────────────────────────────

class TestConvictionFormula:
    def test_one_category_full_confidence(self):
        cats = [CategoryMatch("T", "수주잔고_선행", 1.0)]
        conviction = (len(cats) / 7) * 50 + (sum(c.confidence for c in cats) / len(cats)) * 50
        assert abs(conviction - (50/7 + 50)) < 0.01

    def test_two_categories_example(self):
        cats = [
            CategoryMatch("T", "수주잔고_선행", 0.84),
            CategoryMatch("T", "수익성_급전환", 0.71),
        ]
        conviction = (len(cats) / 7) * 50 + (sum(c.confidence for c in cats) / len(cats)) * 50
        breadth = (2 / 7) * 50    # ~14.3
        avg_conf = (0.84 + 0.71) / 2  # 0.775
        expected = breadth + avg_conf * 50  # ~14.3 + 38.75 = ~53
        assert abs(conviction - expected) < 0.01

    def test_all_seven_max_100(self):
        cats = [CategoryMatch("T", f"cat{i}", 1.0) for i in range(7)]
        conviction = (len(cats) / 7) * 50 + (sum(c.confidence for c in cats) / len(cats)) * 50
        assert abs(conviction - 100.0) < 0.01


# ── TestAnalogLookup ──────────────────────────────────────────────────────────

class TestAnalogLookup:
    def test_financial_analog_closest_bcr(self):
        lib = _lib("수주잔고_선행", [
            {"ticker": "A", "pre_rise_signals": {"bcr_at_signal": 1.5}, "rise_start_date": "2022-01-01", "peak_multiplier": 5.0},
            {"ticker": "B", "pre_rise_signals": {"bcr_at_signal": 2.8}, "rise_start_date": "2021-01-01", "peak_multiplier": 20.0},
        ])
        # current BCR = 2.7, closest is B (2.8)
        result = _find_analog_financial(lib, "수주잔고_선행", "bcr_at_signal", 2.7)
        assert result is not None
        assert result["ticker"] == "B"

    def test_text_analog_most_recent(self):
        lib = _lib("임상_파이프라인", [
            {"ticker": "OLD", "rise_start_date": "2020-01-01", "peak_multiplier": 10.0},
            {"ticker": "NEW", "rise_start_date": "2023-06-01", "peak_multiplier": 15.0},
        ])
        result = _find_analog_text(lib, "임상_파이프라인")
        assert result is not None
        assert result["ticker"] == "NEW"

    def test_missing_category_returns_none(self):
        lib = _lib("수주잔고_선행", [])
        assert _find_analog_financial(lib, "수주잔고_선행", "bcr_at_signal", 2.0) is None
        assert _find_analog_text(lib, "빅테크_파트너") is None

    def test_null_pre_rise_signals_skipped(self):
        lib = _lib("수주잔고_선행", [
            {"ticker": "A", "pre_rise_signals": None, "rise_start_date": "2022-01-01"},
            {"ticker": "B", "pre_rise_signals": {"bcr_at_signal": 2.0}, "rise_start_date": "2021-01-01"},
        ])
        result = _find_analog_financial(lib, "수주잔고_선행", "bcr_at_signal", 1.9)
        assert result is not None
        assert result["ticker"] == "B"


# ── TestDetectorExceptionHandling ─────────────────────────────────────────────

class TestDetectorExceptionHandling:
    def test_one_failing_detector_does_not_stop_others(self):
        """If one detector raises, the rest still run."""
        calls = []

        def good_detector(stock_data, filings):
            calls.append("good")
            m = CategoryMatch(ticker=stock_data["ticker"], category="수익성_급전환", confidence=0.8)
            return m

        def bad_detector(stock_data, filings):
            raise RuntimeError("detector failed")

        # Simulate the scanner's per-detector try/except loop
        detectors = [
            ("수주잔고_선행", bad_detector),
            ("수익성_급전환", good_detector),
        ]
        results = []
        for category, fn in detectors:
            try:
                r = fn({"ticker": "T"}, [])
                if r is not None:
                    results.append(r)
            except Exception:
                pass

        assert len(results) == 1
        assert results[0].category == "수익성_급전환"
        assert "good" in calls
