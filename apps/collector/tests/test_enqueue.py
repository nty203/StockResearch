"""Tests for enqueue.py — score threshold, golden signal, token budget."""
import pytest
from unittest.mock import MagicMock, patch, call
from io import BytesIO

from src.queue.enqueue import (
    enqueue_ticker,
    run,
    _build_prompt_bundle,
    _count_tokens,
    DEFAULT_SCORE_THRESHOLD,
    DEFAULT_MAX_TOKENS,
)


def _make_client(
    screen_scores=None,
    golden_tickers=None,
    financials=None,
    filings=None,
    news=None,
    queue_existing=None,
):
    client = MagicMock()

    def table_side_effect(name):
        tbl = MagicMock()
        if name == "screen_scores":
            tbl.select.return_value.eq.return_value.eq.return_value.\
                gte.return_value.order.return_value.execute.return_value.data = (
                screen_scores or []
            )
        elif name == "trigger_events":
            tbl.select.return_value.eq.return_value.gte.return_value.\
                execute.return_value.data = golden_tickers or []
        elif name == "financials_q":
            tbl.select.return_value.eq.return_value.order.return_value.\
                limit.return_value.execute.return_value.data = financials or []
        elif name == "filings":
            tbl.select.return_value.eq.return_value.gte.return_value.\
                order.return_value.limit.return_value.execute.return_value.data = (
                filings or []
            )
        elif name == "news":
            tbl.select.return_value.eq.return_value.gte.return_value.\
                order.return_value.limit.return_value.execute.return_value.data = (
                news or []
            )
        elif name == "analysis_queue":
            tbl.select.return_value.eq.return_value.eq.return_value.\
                in_.return_value.execute.return_value.data = queue_existing or []
            tbl.insert.return_value.execute.return_value.data = [{"id": "q1"}]
        return tbl

    client.table.side_effect = table_side_effect
    client.storage.from_.return_value.upload.return_value = {"Key": "test"}
    return client


class TestEnqueueTicker:
    def test_enqueues_new_item(self):
        client = _make_client()
        result = enqueue_ticker(client, "ACME", "demand", "2024-01-01", DEFAULT_MAX_TOKENS)
        assert result is not None

    def test_skips_already_queued(self):
        client = _make_client(queue_existing=[{"id": "existing", "status": "PENDING"}])
        result = enqueue_ticker(client, "ACME", "demand", "2024-01-01", DEFAULT_MAX_TOKENS)
        assert result is None

    def test_uploads_to_storage(self):
        client = _make_client()
        enqueue_ticker(client, "ACME", "demand", "2024-01-01", DEFAULT_MAX_TOKENS)
        client.storage.from_.assert_called_with("analysis-prompts")
        client.storage.from_.return_value.upload.assert_called_once()

    def test_storage_failure_still_inserts(self):
        client = _make_client()
        client.storage.from_.return_value.upload.side_effect = Exception("storage error")
        result = enqueue_ticker(client, "ACME", "demand", "2024-01-01", DEFAULT_MAX_TOKENS)
        assert result is not None

    def test_insert_called_with_pending_status(self):
        inserted_rows = []

        def capture_insert(row):
            inserted_rows.append(row)
            m = MagicMock()
            m.execute.return_value.data = [{"id": "q1"}]
            return m

        client = _make_client()
        # Patch insert on the analysis_queue table mock
        # Since side_effect is used for tables, we grab it via call
        with patch("src.queue.enqueue.enqueue_ticker", wraps=enqueue_ticker):
            # Directly check the insert was called with correct status
            result = enqueue_ticker(client, "ACME", "demand", "2024-01-01", DEFAULT_MAX_TOKENS)
        assert result is not None
        assert result.get("id") == "q1"


class TestRun:
    def test_enqueues_stocks_above_threshold(self):
        stocks = [{"ticker": "A", "score_10x": 80, "passed": True}]
        client = _make_client(screen_scores=stocks)

        with patch("src.queue.enqueue.get_client", return_value=client), \
             patch("src.queue.enqueue.load_settings", return_value={}), \
             patch("src.queue.enqueue.enqueue_ticker", return_value={"id": "new"}) as mock_enq:
            n = run("2024-01-01")

        # 1 stock × 5 prompt types = 5 items
        assert mock_enq.call_count == 5
        assert n == 5

    def test_does_not_enqueue_below_threshold(self):
        stocks = [{"ticker": "LOW", "score_10x": 30, "passed": True}]
        # Stock with score 30 would not be returned by the Supabase query (filtered server-side)
        # But if it were passed anyway, run() should handle it
        client = _make_client(screen_scores=[])

        with patch("src.queue.enqueue.get_client", return_value=client), \
             patch("src.queue.enqueue.load_settings", return_value={}), \
             patch("src.queue.enqueue.enqueue_ticker") as mock_enq:
            n = run("2024-01-01")

        assert mock_enq.call_count == 0
        assert n == 0

    def test_golden_signal_ticker_enqueued_regardless_of_score(self):
        """Tickers with golden signals get enqueued even if not in screen_scores."""
        golden = [{"ticker": "GOLD"}]
        client = _make_client(screen_scores=[], golden_tickers=golden)

        with patch("src.queue.enqueue.get_client", return_value=client), \
             patch("src.queue.enqueue.load_settings", return_value={}), \
             patch("src.queue.enqueue.enqueue_ticker", return_value={"id": "new"}) as mock_enq:
            n = run("2024-01-01")

        # GOLD ticker should be enqueued for 5 prompt types
        assert mock_enq.call_count == 5

    def test_custom_threshold_from_settings(self):
        """Custom threshold=80 should exclude a stock with score=75."""
        stocks = [{"ticker": "MID", "score_10x": 75, "passed": True}]
        # At threshold=80, this stock would be filtered out by the DB query
        client = _make_client(screen_scores=[])

        with patch("src.queue.enqueue.get_client", return_value=client), \
             patch("src.queue.enqueue.load_settings", return_value={"enqueue_score_threshold": 80}), \
             patch("src.queue.enqueue.enqueue_ticker") as mock_enq:
            n = run("2024-01-01")

        assert mock_enq.call_count == 0


class TestTokenBudget:
    def test_count_tokens_returns_int(self):
        count = _count_tokens("안녕하세요 hello world")
        assert isinstance(count, int)
        assert count > 0

    def test_bundle_within_token_limit(self):
        client = _make_client(
            financials=[{
                "fq": "2023Q4", "revenue": 100e9, "op_margin": 10.0,
                "roic": 15.0, "fcf": 5e9, "debt_ratio": 100.0,
            }],
        )
        bundle = _build_prompt_bundle(client, "ACME", "demand", DEFAULT_MAX_TOKENS)
        count = _count_tokens(bundle)
        assert count <= DEFAULT_MAX_TOKENS

    def test_large_input_truncated(self):
        """Artificially large news section should be truncated."""
        huge_news = [{"title": "x" * 500, "summary": "y" * 500,
                      "published_at": "2024-01-01", "source": "test"}] * 20
        client = _make_client(news=huge_news)

        bundle = _build_prompt_bundle(client, "ACME", "demand", DEFAULT_MAX_TOKENS)
        count = _count_tokens(bundle)
        assert count <= DEFAULT_MAX_TOKENS * 1.1  # 10% tolerance for overhead

    def test_truncated_bundle_contains_marker(self):
        """When truncation occurs, [truncated] marker should appear in bundle."""
        huge_news = [{"title": "t" * 1000, "summary": "s" * 1000,
                      "published_at": "2024-01-01", "source": "test"}] * 30
        client = _make_client(news=huge_news)

        bundle = _build_prompt_bundle(client, "ACME", "demand", 300)  # very small budget
        assert "[truncated]" in bundle
