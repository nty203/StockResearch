"""Tests for score.py — percentile, weighted sum, market_gate."""
import pytest
from unittest.mock import MagicMock, patch
import pandas as pd

from src.screening.score import (
    compute_scores,
    _categorize_score,
    _compute_market_gate,
    DEFAULT_WEIGHTS,
)


def _make_filter_result(scores: dict, passed: bool = True):
    """Build a mock FilterResult."""
    fr = MagicMock()
    fr.passed = passed
    fr.score = sum(scores.values())
    fr.scores_by_filter = scores
    fr.failed_filters = []
    return fr


def _chain_mock(data):
    """Return a MagicMock that handles .order().limit().execute().data chain."""
    m = MagicMock()
    m.order.return_value.limit.return_value.execute.return_value.data = data
    # Also handle direct .execute().data (no order/limit)
    m.execute.return_value.data = data
    # .single().execute().data
    m.single.return_value.execute.return_value.data = data[0] if data else None
    return m


def _make_supabase_mock(stocks, prices_by_ticker, financials_by_ticker, settings=None):
    """Build a Supabase client mock with stock/price/financial data."""
    client = MagicMock()

    def table_side_effect(name):
        tbl = MagicMock()

        if name == "stocks":
            # List query: .select().eq().execute()
            tbl.select.return_value.eq.return_value.execute.return_value.data = stocks
            # Single query: .select().eq().single().execute()
            tbl.select.return_value.eq.return_value.single.return_value.execute.return_value.data = (
                stocks[0] if stocks else None
            )

        elif name == "prices_daily":
            def prices_chain(ticker_val=None):
                data = prices_by_ticker.get(ticker_val or "", [])
                return _chain_mock(data)

            inner = MagicMock()
            inner.eq.side_effect = lambda col, val: prices_chain(val) if col == "ticker" else _chain_mock([])
            tbl.select.return_value = inner

        elif name == "financials_q":
            def fins_chain(ticker_val=None):
                data = financials_by_ticker.get(ticker_val or "", [])
                return _chain_mock(data)

            inner = MagicMock()
            inner.eq.side_effect = lambda col, val: fins_chain(val) if col == "ticker" else _chain_mock([])
            tbl.select.return_value = inner

        elif name == "settings":
            settings_data = [
                {"key": k, "value_json": v}
                for k, v in (settings or {}).items()
            ]
            tbl.select.return_value.execute.return_value.data = settings_data

        elif name == "screen_scores":
            tbl.upsert.return_value.execute.return_value.data = []

        return tbl

    client.table.side_effect = table_side_effect
    return client


class TestComputeScores:
    def _run_with_mock(self, stocks, prices, fins, settings=None):
        client = _make_supabase_mock(stocks, prices, fins, settings)
        with patch("src.screening.score.get_client", return_value=client), \
             patch("src.screening.score.load_settings", return_value=settings or {}), \
             patch("src.screening.score._compute_market_gate", return_value=1.0), \
             patch("src.screening.score.apply_kr_filters") as mock_kr, \
             patch("src.screening.score.apply_us_filters") as mock_us:

            def make_passing(stock_data, settings=None):
                return _make_filter_result({"f03": 20, "f11_rs": 15, "f05_op_margin": 10})

            mock_kr.side_effect = make_passing
            mock_us.side_effect = make_passing

            return compute_scores("2024-01-01")

    def test_percentile_range_0_to_100(self):
        stocks = [{"ticker": f"K{i:03d}", "market": "KOSPI"} for i in range(5)]
        prices = {s["ticker"]: [{"close": 10000, "volume": 100000}] * 252 for s in stocks}
        fins = {s["ticker"]: [{"fq": "2023Q4", "revenue": 100e9, "op_margin": 10.0,
                                "roic": 15.0, "fcf": 5e9, "debt_ratio": 100.0}] * 8
                for s in stocks}

        rows = self._run_with_mock(stocks, prices, fins)
        passed = [r for r in rows if r["passed"]]
        assert len(passed) > 0

        percentiles = [r["percentile"] for r in passed]
        assert all(0 <= p <= 100 for p in percentiles)

    def test_weighted_sum_capped_at_100(self):
        stocks = [{"ticker": "KRW001", "market": "KOSPI"}]
        prices = {"KRW001": [{"close": 50000, "volume": 200000}] * 252}
        fins = {"KRW001": [{"fq": "2023Q4", "revenue": 300e9, "op_margin": 25.0,
                             "roic": 30.0, "fcf": 20e9, "debt_ratio": 80.0}] * 8}

        rows = self._run_with_mock(stocks, prices, fins)
        for r in rows:
            assert r.get("score_10x", 0) <= 100

    def test_market_gate_07_applied(self):
        stocks = [{"ticker": "KRW002", "market": "KOSPI"}]
        prices = {"KRW002": [{"close": 10000, "volume": 100000}] * 252}
        fins = {"KRW002": [{"fq": "2023Q4", "revenue": 100e9, "op_margin": 10.0,
                             "roic": 15.0, "fcf": 5e9, "debt_ratio": 100.0}] * 8}

        client = _make_supabase_mock(stocks, prices, fins)
        with patch("src.screening.score.get_client", return_value=client), \
             patch("src.screening.score.load_settings", return_value={}), \
             patch("src.screening.score._compute_market_gate", return_value=0.7), \
             patch("src.screening.score.apply_kr_filters") as mock_kr, \
             patch("src.screening.score.apply_us_filters") as mock_us:

            mock_kr.side_effect = lambda s, settings=None: _make_filter_result({"f03": 20})
            mock_us.side_effect = lambda s, settings=None: _make_filter_result({"us03": 20})

            rows = compute_scores("2024-01-01")
            for r in rows:
                assert r["market_gate"] == 0.7

    def test_failed_stock_score_zero(self):
        stocks = [{"ticker": "KRW003", "market": "KOSPI"}]
        prices = {}
        fins = {}

        client = _make_supabase_mock(stocks, prices, fins)
        with patch("src.screening.score.get_client", return_value=client), \
             patch("src.screening.score.load_settings", return_value={}), \
             patch("src.screening.score._compute_market_gate", return_value=1.0), \
             patch("src.screening.score.apply_kr_filters") as mock_kr:

            def failed_filter(stock_data, settings=None):
                fr = MagicMock()
                fr.passed = False
                fr.score = 0.0
                fr.scores_by_filter = {}
                fr.failed_filters = ["f01"]
                return fr

            mock_kr.side_effect = failed_filter

            rows = compute_scores("2024-01-01")
            assert all(r["score_10x"] == 0 for r in rows)

    def test_empty_universe_returns_empty(self):
        client = _make_supabase_mock([], {}, {})
        with patch("src.screening.score.get_client", return_value=client), \
             patch("src.screening.score.load_settings", return_value={}), \
             patch("src.screening.score._compute_market_gate", return_value=1.0):
            rows = compute_scores("2024-01-01")
            assert rows == []


class TestCategorizeScore:
    def test_growth_category(self):
        fr = _make_filter_result({"f03": 20, "f04": 10})
        cats = _categorize_score(50, fr)
        assert cats["growth"] > 0

    def test_momentum_category(self):
        fr = _make_filter_result({"f11_rs": 10, "f12_momentum": 8})
        cats = _categorize_score(18, fr)
        assert cats["momentum"] > 0

    def test_all_categories_present(self):
        fr = _make_filter_result({})
        cats = _categorize_score(0, fr)
        for cat in DEFAULT_WEIGHTS:
            assert cat in cats

    def test_categories_not_exceeding_100(self):
        fr = _make_filter_result({k: 200 for k in ["f03", "f04", "f11_rs", "f12_momentum"]})
        cats = _categorize_score(800, fr)
        for cat, val in cats.items():
            assert val <= 100, f"{cat} exceeded 100: {val}"


class TestMarketGate:
    def test_returns_float(self):
        client = MagicMock()
        client.table.return_value.select.return_value.eq.return_value.\
            order.return_value.limit.return_value.execute.return_value.data = []
        result = _compute_market_gate(client)
        assert isinstance(result, float)

    def test_returns_07_when_below_ma200(self):
        # current (prices[0]) must be BELOW MA200 to trigger 0.7
        # prices[0] = 1 (current), rest = 200 (historical high) → MA200 ≈ 200 > 1
        prices = [{"close": 1.0}] + [{"close": 200.0}] * 200
        client = MagicMock()
        client.table.return_value.select.return_value.eq.return_value.\
            order.return_value.limit.return_value.execute.return_value.data = prices
        result = _compute_market_gate(client)
        assert result == 0.7

    def test_returns_10_on_exception(self):
        client = MagicMock()
        client.table.side_effect = Exception("DB error")
        result = _compute_market_gate(client)
        assert result == 1.0
