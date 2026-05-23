"""Tests for auto_populate orchestrator — mocked sub-modules."""
import pytest
from unittest.mock import patch, MagicMock

from src.hundredx.auto_populate import run


class TestAutoPopulateRun:
    def test_calls_all_three_steps_in_order(self):
        mock_stock = MagicMock()
        with (
            patch("src.hundredx.auto_populate.discover.run", return_value=[mock_stock, mock_stock]) as disc,
            patch("src.hundredx.auto_populate.backfill_history.run", return_value=15) as bf,
            patch("src.hundredx.auto_populate.extract_signals.run", return_value=3) as ext,
            patch("src.hundredx.auto_populate.analyze_library_pptr.run", return_value=1) as pptr,
        ):
            discovered, backfilled, extracted, pptr_count = run(years=5, min_multiplier=50.0)

        assert discovered == 2
        assert backfilled == 15
        assert extracted == 3
        disc.assert_called_once_with(years=5, min_multiplier=50.0, auto_insert=True)
        bf.assert_called_once()
        ext.assert_called_once_with(force=True)  # force=True when backfill > 0

    def test_skip_backfill_flag_works(self):
        with (
            patch("src.hundredx.auto_populate.discover.run", return_value=[]) as disc,
            patch("src.hundredx.auto_populate.backfill_history.run", return_value=0) as bf,
            patch("src.hundredx.auto_populate.extract_signals.run", return_value=1) as ext,
            patch("src.hundredx.auto_populate.analyze_library_pptr.run", return_value=1) as pptr,
        ):
            discovered, backfilled, extracted, pptr_count = run(skip_backfill=True)

        bf.assert_not_called()
        assert backfilled == 0
        # force=False when backfill was skipped (backfilled=0)
        ext.assert_called_once_with(force=False)

    def test_extract_force_false_when_no_backfill(self):
        with (
            patch("src.hundredx.auto_populate.discover.run", return_value=[]),
            patch("src.hundredx.auto_populate.backfill_history.run", return_value=0),
            patch("src.hundredx.auto_populate.extract_signals.run", return_value=0) as ext,
            patch("src.hundredx.auto_populate.analyze_library_pptr.run", return_value=0) as pptr,
        ):
            run()

        ext.assert_called_once_with(force=False)

    def test_returns_tuple_of_counts(self):
        with (
            patch("src.hundredx.auto_populate.discover.run", return_value=["a", "b", "c"]),
            patch("src.hundredx.auto_populate.backfill_history.run", return_value=42),
            patch("src.hundredx.auto_populate.extract_signals.run", return_value=7),
            patch("src.hundredx.auto_populate.analyze_library_pptr.run", return_value=2),
        ):
            result = run()

        assert result == (3, 42, 7, 2)

    def test_min_multiplier_forwarded_to_discover(self):
        with (
            patch("src.hundredx.auto_populate.discover.run", return_value=[]) as disc,
            patch("src.hundredx.auto_populate.backfill_history.run", return_value=0),
            patch("src.hundredx.auto_populate.extract_signals.run", return_value=0),
            patch("src.hundredx.auto_populate.analyze_library_pptr.run", return_value=0),
        ):
            run(years=3, min_multiplier=30.0)

        disc.assert_called_once_with(years=3, min_multiplier=30.0, auto_insert=True)
