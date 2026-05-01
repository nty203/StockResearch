"""Tests for hundredx discover module — pure algorithm unit tests (no external calls)."""
import pytest
from src.hundredx.discover import _find_best_multiplier, DiscoveredStock


class TestFindBestMultiplier:
    def test_simple_monotone_rise(self):
        prices = [("2020-01-01", 100.0), ("2020-06-01", 500.0), ("2021-01-01", 1000.0)]
        mult, trough_d, trough_p, peak_d, peak_p = _find_best_multiplier(prices)
        assert abs(mult - 10.0) < 0.01
        assert trough_d == "2020-01-01"
        assert peak_d == "2021-01-01"
        assert trough_p == 100.0
        assert peak_p == 1000.0

    def test_finds_best_trough_before_peak(self):
        # Prices: 100 → 200 → 50 → 5000 — best is 50→5000 = 100x
        prices = [
            ("2020-01-01", 100.0),
            ("2020-06-01", 200.0),
            ("2020-09-01", 50.0),
            ("2021-01-01", 5000.0),
        ]
        mult, trough_d, _, peak_d, _ = _find_best_multiplier(prices)
        assert abs(mult - 100.0) < 0.01
        assert trough_d == "2020-09-01"
        assert peak_d == "2021-01-01"

    def test_running_min_resets_after_new_low(self):
        # 100 → 50 (new low) → 200 → 30 (new low) → 3000 — best is 30→3000 = 100x
        prices = [
            ("2020-01-01", 100.0),
            ("2020-03-01", 50.0),
            ("2020-06-01", 200.0),
            ("2020-09-01", 30.0),
            ("2021-01-01", 3000.0),
        ]
        mult, trough_d, _, _, _ = _find_best_multiplier(prices)
        assert abs(mult - 100.0) < 0.01
        assert trough_d == "2020-09-01"

    def test_single_price_returns_zero(self):
        prices = [("2020-01-01", 100.0)]
        mult, _, _, _, _ = _find_best_multiplier(prices)
        assert mult == 0.0

    def test_empty_prices_returns_zero(self):
        mult, _, _, _, _ = _find_best_multiplier([])
        assert mult == 0.0

    def test_zero_and_negative_prices_skipped(self):
        prices = [
            ("2020-01-01", 0.0),
            ("2020-02-01", -50.0),
            ("2020-03-01", 100.0),
            ("2020-06-01", 1000.0),
        ]
        mult, _, trough_p, _, _ = _find_best_multiplier(prices)
        # Should use first valid positive price as base
        assert mult > 0
        assert trough_p > 0

    def test_monotone_decline(self):
        prices = [("2020-01-01", 1000.0), ("2020-06-01", 500.0), ("2021-01-01", 100.0)]
        mult, _, _, _, _ = _find_best_multiplier(prices)
        # No upward move: running min never leads to multiplier > 1
        assert mult < 2.0

    def test_two_x_rise_detectable(self):
        prices = [("2020-01-01", 1000.0), ("2021-01-01", 2000.0)]
        mult, _, _, _, _ = _find_best_multiplier(prices)
        assert abs(mult - 2.0) < 0.01

    def test_returns_first_of_equal_troughs(self):
        # Two troughs of equal depth; first one should win (running min doesn't reset on equal)
        prices = [
            ("2020-01-01", 100.0),
            ("2020-06-01", 100.0),
            ("2021-01-01", 500.0),
        ]
        mult, trough_d, _, _, _ = _find_best_multiplier(prices)
        assert mult == 5.0
        # First 100 seen first → running_min_date is "2020-01-01"
        assert trough_d == "2020-01-01"


class TestDiscoveredStockDataclass:
    def test_fields_accessible(self):
        d = DiscoveredStock(
            ticker="012450",
            multiplier=100.0,
            trough_date="2020-01-01",
            trough_price=1000.0,
            peak_date="2023-01-01",
            peak_price=100000.0,
            years_to_peak=3.0,
        )
        assert d.ticker == "012450"
        assert d.multiplier == 100.0
        assert d.years_to_peak == 3.0
