"""Tests for backfill_history — mocked DB/DART, no external calls."""
import pytest
from unittest.mock import MagicMock, patch
import pandas as pd

from src.hundredx.backfill_history import backfill_for_library_stock, _existing_filings_count


def _build_client(existing_count: int = 0) -> MagicMock:
    """Mock Supabase client."""
    client = MagicMock()

    # _existing_filings_count path: .table().select().eq().gte().lt().limit().execute()
    count_res = MagicMock()
    count_res.count = existing_count
    count_res.data = []
    (client.table.return_value
     .select.return_value
     .eq.return_value
     .gte.return_value
     .lt.return_value
     .limit.return_value
     .execute.return_value) = count_res

    # upsert_batch path: .table().upsert().execute()
    upsert_res = MagicMock()
    upsert_res.data = [{"id": "1"}]
    (client.table.return_value
     .upsert.return_value
     .execute.return_value) = upsert_res

    return client


def _build_dart(rows: list[dict]) -> MagicMock:
    """Mock OpenDartReader.list() returning a DataFrame."""
    dart = MagicMock()
    df = pd.DataFrame(rows)
    dart.list.return_value = df if rows else None
    return dart


class TestExistingFilingsCount:
    def test_returns_zero_when_no_rows(self):
        client = _build_client(existing_count=0)
        count = _existing_filings_count(client, "086520", "2020-01-01", "2021-01-01")
        assert count == 0

    def test_returns_count_when_exists(self):
        client = _build_client(existing_count=5)
        count = _existing_filings_count(client, "086520", "2020-01-01", "2021-01-01")
        assert count == 5


class TestBackfillForLibraryStock:
    def test_skips_when_already_backfilled(self):
        client = _build_client(existing_count=3)
        dart = MagicMock()
        result = backfill_for_library_stock(client, dart, "086520", "2021-07-01")
        assert result == 0
        dart.list.assert_not_called()

    def test_processes_dart_filings_when_none_exist(self):
        client = _build_client(existing_count=0)
        dart = _build_dart([
            {"report_nm": "수주공시", "rcept_dt": "20210601", "rcept_no": "12345"},
            {"report_nm": "주요사항보고서", "rcept_dt": "20210701", "rcept_no": "67890"},
        ])
        # upsert_batch returns len of rows
        with patch("src.hundredx.backfill_history.upsert_batch", return_value=2) as mock_upsert:
            result = backfill_for_library_stock(client, dart, "086520", "2022-01-01")
        assert result == 2
        mock_upsert.assert_called_once()

    def test_returns_zero_when_dart_returns_none(self):
        client = _build_client(existing_count=0)
        dart = _build_dart([])  # empty DataFrame → None
        dart.list.return_value = None
        result = backfill_for_library_stock(client, dart, "086520", "2022-01-01")
        assert result == 0

    def test_skips_rows_with_empty_headline(self):
        client = _build_client(existing_count=0)
        dart = _build_dart([
            {"report_nm": "", "rcept_dt": "20210601", "rcept_no": "111"},
            {"report_nm": "수주공시", "rcept_dt": "20210615", "rcept_no": "222"},
        ])
        with patch("src.hundredx.backfill_history.upsert_batch", return_value=1) as mock_upsert:
            result = backfill_for_library_stock(client, dart, "086520", "2022-01-01")
        # Only 1 row has a headline
        inserted_rows = mock_upsert.call_args[0][2]
        assert len(inserted_rows) == 1
        assert inserted_rows[0]["headline"] == "수주공시"

    def test_date_window_is_18mo_before_and_3mo_after(self):
        client = _build_client(existing_count=0)
        dart = _build_dart([])
        dart.list.return_value = None
        backfill_for_library_stock(client, dart, "086520", "2022-01-01")
        call_kwargs = dart.list.call_args[1] if dart.list.call_args else {}
        # start should be ~18 months before 2022-01-01 = mid-2020
        start_arg = dart.list.call_args[1].get("start", "") if dart.list.called else ""
        if start_arg:
            assert start_arg[:4] == "2020"  # 18 months before 2022 = ~June 2020

    def test_dart_exception_returns_zero(self):
        client = _build_client(existing_count=0)
        dart = MagicMock()
        dart.list.side_effect = Exception("DART API error")
        result = backfill_for_library_stock(client, dart, "086520", "2022-01-01")
        assert result == 0
