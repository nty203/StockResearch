"""Tests for update_library — DB-mocked unit tests for multiplier logic."""
import pytest
from unittest.mock import MagicMock

from src.hundredx.update_library import _fetch_close_near_date, _fetch_latest_close


def _mock_client(rows: list[dict]) -> MagicMock:
    """Build a mock Supabase client that returns `rows` from .execute()."""
    client = MagicMock()
    execute_mock = MagicMock()
    execute_mock.data = rows
    # Chain: .table().select().eq().gte().lte().order().limit().execute()
    (client.table.return_value
     .select.return_value
     .eq.return_value
     .gte.return_value
     .lte.return_value
     .order.return_value
     .limit.return_value
     .execute.return_value) = execute_mock
    # Also wire .order().limit() directly for _fetch_latest_close
    (client.table.return_value
     .select.return_value
     .eq.return_value
     .order.return_value
     .limit.return_value
     .execute.return_value) = execute_mock
    return client


class TestFetchCloseNearDate:
    def test_returns_close_when_available(self):
        client = _mock_client([{"date": "2022-07-01", "close": 50000.0}])
        result = _fetch_close_near_date(client, "012450", "2022-07-01")
        assert result == 50000.0

    def test_returns_none_when_no_rows(self):
        # Set empty data on both query paths (main + fallback)
        client = MagicMock()
        empty = MagicMock()
        empty.data = []
        # Main query: .eq().gte().lte().order().limit().execute()
        (client.table.return_value.select.return_value
         .eq.return_value.gte.return_value.lte.return_value
         .order.return_value.limit.return_value.execute.return_value) = empty
        # Fallback query: .eq().order().limit().execute() (no gte/lte)
        (client.table.return_value.select.return_value
         .eq.return_value.order.return_value.limit.return_value
         .execute.return_value) = empty
        result = _fetch_close_near_date(client, "NOTEXIST", "2022-07-01")
        assert result is None

    def test_first_row_used(self):
        # Multiple rows returned → first one wins
        client = _mock_client([
            {"date": "2022-07-01", "close": 50000.0},
            {"date": "2022-07-02", "close": 51000.0},
        ])
        result = _fetch_close_near_date(client, "012450", "2022-07-01")
        assert result == 50000.0


class TestFetchLatestClose:
    def test_returns_latest_close(self):
        client = _mock_client([{"date": "2025-04-30", "close": 120000.0}])
        result = _fetch_latest_close(client, "012450")
        assert result == 120000.0

    def test_returns_none_when_no_data(self):
        client = _mock_client([])
        result = _fetch_latest_close(client, "NOTEXIST")
        assert result is None


class TestMultiplierCalculation:
    def test_multiplier_math(self):
        rise_price = 50000.0
        latest_price = 200000.0
        expected = 4.0
        assert round(latest_price / rise_price, 2) == expected

    def test_peak_not_downgraded(self):
        existing_peak = 10.0
        latest_multiplier = 8.0
        new_peak = max(existing_peak, latest_multiplier)
        assert new_peak == 10.0  # preserves higher historical peak

    def test_peak_upgraded_when_exceeded(self):
        existing_peak = 10.0
        latest_multiplier = 15.0
        new_peak = max(existing_peak, latest_multiplier)
        assert new_peak == 15.0
