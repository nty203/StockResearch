"""Tests for settings_loader.py — Supabase mock → settings fetch + override."""
import pytest
from unittest.mock import MagicMock

from src.screening.settings_loader import load_settings


def _make_client(settings_data: list[dict]) -> MagicMock:
    """Build mock Supabase client returning settings_data."""
    client = MagicMock()
    client.table.return_value.select.return_value.execute.return_value.data = settings_data
    return client


class TestLoadSettings:
    def test_returns_dict(self):
        client = _make_client([])
        result = load_settings(client)
        assert isinstance(result, dict)

    def test_fetches_key_value(self):
        client = _make_client([
            {"key": "kr_min_market_cap", "value_json": 300_000_000_000},
        ])
        result = load_settings(client)
        assert result["kr_min_market_cap"] == 300_000_000_000

    def test_multiple_keys(self):
        client = _make_client([
            {"key": "kr_min_market_cap", "value_json": 300_000_000_000},
            {"key": "us_min_market_cap", "value_json": 500_000_000},
            {"key": "enqueue_score_threshold", "value_json": 65},
        ])
        result = load_settings(client)
        assert len(result) == 3
        assert result["enqueue_score_threshold"] == 65

    def test_json_object_value(self):
        client = _make_client([
            {"key": "score_weights", "value_json": {"growth": 28, "momentum": 22}},
        ])
        result = load_settings(client)
        assert result["score_weights"]["growth"] == 28

    def test_bool_value(self):
        client = _make_client([
            {"key": "market_gate_enabled", "value_json": True},
        ])
        result = load_settings(client)
        assert result["market_gate_enabled"] is True

    def test_numeric_string_value(self):
        # Supabase JSONB returns Python types directly; a stored integer stays integer
        client = _make_client([
            {"key": "telegram_chat_id", "value_json": 12345678},
        ])
        result = load_settings(client)
        assert result["telegram_chat_id"] == 12345678

    def test_empty_settings_returns_empty_dict(self):
        client = _make_client([])
        result = load_settings(client)
        assert result == {}

    def test_none_data_returns_empty_dict(self):
        client = MagicMock()
        client.table.return_value.select.return_value.execute.return_value.data = None
        result = load_settings(client)
        assert result == {}

    def test_exception_returns_empty_dict(self):
        client = MagicMock()
        client.table.side_effect = Exception("DB error")
        result = load_settings(client)
        assert result == {}

    def test_override_in_filters_kr(self):
        """Settings override should be used in apply_kr_filters threshold."""
        from src.screening.filters_kr import apply_kr_filters

        client = _make_client([
            {"key": "kr_min_market_cap", "value_json": 5_000_000_000_000},  # very high
        ])
        settings = load_settings(client)

        stock = {
            "ticker": "123456",
            "market_cap": 1_000_000_000_000,  # 1조 — would pass default but fail custom
            "avg_daily_value": 10_000_000_000,
            "revenue_ttm": 200_000_000_000,
            "revenue_prev": 150_000_000_000,
            "op_margin_ttm": 8.0,
            "debt_ratio": 100.0,
        }
        result = apply_kr_filters(stock, settings)
        assert result.passed is False
        assert "f01_market_cap" in result.failed_filters

    def test_override_threshold_in_filters_us(self):
        """Settings can lower US revenue growth threshold."""
        from src.screening.filters_us import apply_us_filters

        # Set threshold to 5% — borderline stock at 8% growth should now pass
        settings = {"us_min_revenue_growth": 5.0}

        stock = {
            "ticker": "SLOW",
            "market_cap": 2_000_000_000,
            "avg_daily_value": 10_000_000,
            "revenue_ttm": 108_000_000,
            "revenue_prev": 100_000_000,  # 8% growth
            "gross_margin": 55.0,
            "debt_equity": 80.0,
        }
        result = apply_us_filters(stock, settings)
        assert result.passed is True
