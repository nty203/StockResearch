"""Regression test for utils/settings.py (moved from screening/settings_loader.py).

Validates load_settings() behavior in its new location: same contract as before
the project reduction PR.
"""
from unittest.mock import MagicMock

from src.utils.settings import load_settings


def _mock_client(rows: list[dict] | Exception):
    """Build a Supabase client mock that returns the given rows or raises."""
    client = MagicMock()
    chain = client.table.return_value.select.return_value.execute
    if isinstance(rows, Exception):
        chain.side_effect = rows
    else:
        result = MagicMock()
        result.data = rows
        chain.return_value = result
    return client


def test_happy_path_returns_dict():
    client = _mock_client([
        {"key": "filings_lookback_days", "value_json": 2},
        {"key": "score_weights", "value_json": {"growth": 28, "momentum": 22}},
    ])
    cfg = load_settings(client)
    assert cfg["filings_lookback_days"] == 2
    assert cfg["score_weights"] == {"growth": 28, "momentum": 22}


def test_empty_table_returns_empty_dict():
    client = _mock_client([])
    cfg = load_settings(client)
    assert cfg == {}


def test_string_value_parses_json():
    client = _mock_client([
        {"key": "thresholds", "value_json": '{"min": 0.5, "max": 0.9}'},
    ])
    cfg = load_settings(client)
    assert cfg["thresholds"] == {"min": 0.5, "max": 0.9}


def test_string_value_invalid_json_preserves_string():
    client = _mock_client([
        {"key": "label", "value_json": "not-json-at-all"},
    ])
    cfg = load_settings(client)
    assert cfg["label"] == "not-json-at-all"


def test_db_exception_returns_empty_dict():
    client = _mock_client(RuntimeError("connection refused"))
    cfg = load_settings(client)
    assert cfg == {}
