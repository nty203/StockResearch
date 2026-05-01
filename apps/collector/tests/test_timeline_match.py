"""Tests for timeline matching engine."""
from datetime import datetime, timedelta

from src.hundredx.timeline_match import (
    evaluate_timeline,
    best_timeline_in_category,
    _check_trigger_fired,
)


def _filing(headline: str, raw_text: str = "", days_ago: int = 30,
            parsed_amount: float | None = None) -> dict:
    filed_at = (datetime.utcnow() - timedelta(days=days_ago)).isoformat()
    return {
        "id": f"f{days_ago}", "ticker": "T",
        "headline": headline, "raw_text": raw_text,
        "filed_at": filed_at, "parsed_amount": parsed_amount,
    }


def _hanwha_lib_with_timeline() -> dict:
    return {
        "ticker": "012450",
        "category": "수주잔고_선행",
        "peak_multiplier": 20.0,
        "rise_start_date": "2022-07-01",
        "triggers": [
            {
                "seq": 0, "name": "지정학적_배경 (T-12)", "months_from_rise": -12, "weight": 0.5,
                "signals": {"keywords": ["NATO", "재무장"], "min_keyword_matches": 1, "sector_required": "방산"},
            },
            {
                "seq": 1, "name": "초기_수주 (T-9)", "months_from_rise": -9, "weight": 1.0,
                "signals": {"keywords": ["수출", "방산", "K-9"], "min_keyword_matches": 2, "sector_required": "방산"},
            },
            {
                "seq": 2, "name": "메가계약 (T-3)", "months_from_rise": -3, "weight": 1.5,
                "signals": {
                    "keywords": ["폴란드", "K-9", "조원"], "min_keyword_matches": 2,
                    "amount_threshold_billions": 9000, "sector_required": "방산",
                },
            },
            {
                "seq": 3, "name": "BCR_급등 (T+3)", "months_from_rise": 3, "weight": 1.5,
                "signals": {"quant": {"bcr_at_signal": 2.0}},
            },
        ],
    }


class TestTriggerFired:
    def test_trigger_fires_on_keyword_match(self):
        trigger = {
            "seq": 0, "name": "test", "months_from_rise": -12, "weight": 1.0,
            "signals": {"keywords": ["NATO", "재무장"], "min_keyword_matches": 1, "sector_required": "방산"},
        }
        stock = {"ticker": "T", "sector_tag": "방산"}
        filings = [_filing("NATO 재무장 방산예산 확대", days_ago=60)]
        ok, ft = _check_trigger_fired(trigger, stock, {}, filings)
        assert ok
        assert ft is not None
        assert ft.fired_at_months_ago is not None
        assert 1.5 < ft.fired_at_months_ago < 2.5

    def test_wrong_sector_blocks_trigger(self):
        trigger = {
            "seq": 0, "name": "test", "months_from_rise": -12, "weight": 1.0,
            "signals": {"keywords": ["NATO"], "min_keyword_matches": 1, "sector_required": "방산"},
        }
        stock = {"ticker": "T", "sector_tag": "IT"}
        filings = [_filing("NATO 재무장")]
        ok, _ = _check_trigger_fired(trigger, stock, {}, filings)
        assert not ok

    def test_amount_threshold_required(self):
        trigger = {
            "seq": 0, "name": "test", "months_from_rise": 0, "weight": 1.0,
            "signals": {
                "keywords": ["폴란드", "K-9"], "min_keyword_matches": 2,
                "amount_threshold_billions": 9000, "sector_required": "방산",
            },
        }
        stock = {"ticker": "T", "sector_tag": "방산"}
        # Below threshold
        filings = [_filing("폴란드 K-9 수주 5000억", parsed_amount=5000)]
        ok, _ = _check_trigger_fired(trigger, stock, {}, filings)
        assert not ok
        # Above threshold
        filings = [_filing("폴란드 K-9 수주 9000억", parsed_amount=9000)]
        ok, _ = _check_trigger_fired(trigger, stock, {}, filings)
        assert ok


class TestEvaluateTimeline:
    def test_partial_timeline_progress(self):
        """Stock fired first 2 triggers but not yet the BCR/amount ones."""
        stock = {"ticker": "T", "sector_tag": "방산"}
        filings = [
            _filing("NATO 재무장 방산예산", days_ago=300),
            _filing("K-9 수출 방산 계약", days_ago=120),
        ]
        progress = evaluate_timeline(stock, filings, _hanwha_lib_with_timeline())
        assert progress is not None
        assert len(progress.fired_triggers) == 2
        assert progress.fired_triggers[0].seq == 0
        assert progress.fired_triggers[1].seq == 1
        # Score = (0.5 + 1.0) / (0.5 + 1.0 + 1.5 + 1.5) = 1.5/4.5 = 0.333
        assert abs(progress.trajectory_score - 0.333) < 0.01
        # Current position = T-9 (latest fired), next expected = T-3
        assert progress.current_position_months == -9
        assert progress.next_expected is not None
        assert progress.next_expected["seq"] == 2

    def test_full_timeline_with_bcr(self):
        stock = {
            "ticker": "T", "sector_tag": "방산",
            "order_backlog": 2_500, "revenue_ttm": 1_000,
        }
        filings = [
            _filing("NATO 재무장", days_ago=350),
            _filing("K-9 방산 수출", days_ago=180),
            _filing("폴란드 K-9 9조원 수출", days_ago=60, parsed_amount=9000),
        ]
        progress = evaluate_timeline(stock, filings, _hanwha_lib_with_timeline())
        assert progress is not None
        # BCR=2.5 ≥ 2.0 → seq=3 fires too
        seqs = [t.seq for t in progress.fired_triggers]
        assert 0 in seqs and 1 in seqs and 2 in seqs and 3 in seqs
        assert progress.trajectory_score == 1.0  # all fired

    def test_no_triggers_returns_none(self):
        stock = {"ticker": "T", "sector_tag": "방산"}
        filings = [_filing("일반 영업 공시", days_ago=30)]
        progress = evaluate_timeline(stock, filings, _hanwha_lib_with_timeline())
        assert progress is None

    def test_no_timeline_in_lib_returns_none(self):
        lib_no_triggers = {"ticker": "X", "category": "수주잔고_선행", "triggers": []}
        progress = evaluate_timeline({"ticker": "T"}, [], lib_no_triggers)
        assert progress is None


class TestBestTimelineInCategory:
    def test_picks_best_trajectory(self):
        lib_a = _hanwha_lib_with_timeline()
        lib_b = {**_hanwha_lib_with_timeline(), "ticker": "267260"}
        # Make B's trigger keywords not match (different keywords)
        lib_b["triggers"] = [
            {"seq": 0, "name": "X", "months_from_rise": 0, "weight": 1.0,
             "signals": {"keywords": ["zzz_unmatched_keyword"], "min_keyword_matches": 1}},
        ]
        stock = {"ticker": "T", "sector_tag": "방산"}
        filings = [_filing("NATO 재무장 K-9 방산 수출", days_ago=100)]
        result = best_timeline_in_category(stock, filings, [lib_a, lib_b], "수주잔고_선행")
        assert result is not None
        assert result.library_ticker == "012450"
