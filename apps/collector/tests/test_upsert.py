"""Tests for upsert.py — idempotency (same data twice → no duplicate rows)."""
import os
import pytest
from unittest.mock import MagicMock, patch, call

from src.upsert import upsert_batch, get_client


class TestUpsertBatch:
    def _make_client(self):
        client = MagicMock()
        upsert_mock = MagicMock()
        upsert_mock.execute.return_value.data = [{"id": 1}, {"id": 2}]
        client.table.return_value.upsert.return_value = upsert_mock
        return client

    def test_returns_count(self):
        client = self._make_client()
        rows = [{"ticker": "ACME", "date": "2024-01-01", "close": 100.0}]
        count = upsert_batch(client, "prices_daily", rows)
        assert count == 2  # from mock data length

    def test_upsert_called_with_rows(self):
        client = self._make_client()
        rows = [
            {"ticker": "A", "date": "2024-01-01"},
            {"ticker": "B", "date": "2024-01-01"},
        ]
        upsert_batch(client, "test_table", rows)
        client.table.assert_called_with("test_table")
        client.table.return_value.upsert.assert_called_once()

    def test_second_upsert_same_data_idempotent(self):
        """Calling upsert twice with same data should call upsert twice (DB handles dedup)."""
        client = self._make_client()
        rows = [{"ticker": "ACME", "date": "2024-01-01", "close": 100.0}]

        count1 = upsert_batch(client, "prices_daily", rows)
        count2 = upsert_batch(client, "prices_daily", rows)

        assert count1 == count2
        assert client.table.return_value.upsert.call_count == 2

    def test_empty_rows_returns_zero(self):
        client = self._make_client()
        count = upsert_batch(client, "prices_daily", [])
        assert count == 0
        client.table.return_value.upsert.assert_not_called()

    def test_upsert_with_on_conflict(self):
        client = self._make_client()
        rows = [{"ticker": "ACME", "run_date": "2024-01-01"}]
        upsert_batch(client, "screen_scores", rows, on_conflict="ticker,run_date")

        call_args = client.table.return_value.upsert.call_args
        assert call_args is not None
        # on_conflict should be passed as kwarg
        kwargs = call_args.kwargs if call_args.kwargs else {}
        args = call_args.args if call_args.args else ()
        # Either kwarg or positional arg contains on_conflict value
        assert "ticker,run_date" in str(call_args)

    def test_batches_large_sets(self):
        """Large row sets should be split into batches of 500."""
        client = self._make_client()
        client.table.return_value.upsert.return_value.execute.return_value.data = [{"id": i} for i in range(500)]

        rows = [{"ticker": f"T{i}", "date": "2024-01-01"} for i in range(1200)]
        upsert_batch(client, "prices_daily", rows)

        # Should be called ceil(1200/500) = 3 times
        assert client.table.return_value.upsert.call_count == 3

    def test_returns_zero_on_exception(self):
        client = MagicMock()
        client.table.return_value.upsert.side_effect = Exception("DB error")

        rows = [{"ticker": "ACME"}]
        count = upsert_batch(client, "prices_daily", rows)
        assert count == 0


class TestGetClient:
    def test_raises_without_env(self, monkeypatch):
        monkeypatch.delenv("SUPABASE_URL", raising=False)
        monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
        with pytest.raises(Exception):
            get_client()

    def test_returns_client_with_env(self, monkeypatch):
        monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test-key-123")
        with patch("src.upsert.create_client") as mock_create:
            mock_create.return_value = MagicMock()
            client = get_client()
            assert client is not None
            mock_create.assert_called_once_with(
                "https://test.supabase.co", "test-key-123"
            )
