from datetime import datetime, timezone

from src.hundredx.pptr_confidence import compute_pptr_confidence


def _score(rule, matched_conditions, stock=None):
    return compute_pptr_confidence(
        rule=rule,
        matched_conditions=matched_conditions,
        evidence=[{"date": "2026-01-01"}],
        stock_data=stock or {},
        now=datetime(2026, 5, 23, tzinfo=timezone.utc),
    )


def test_rule_performance_history_lifts_confidence():
    rule = {
        "category": "수주잔고_선행",
        "conditions": {"bcr_at_signal": 1.5, "keywords": ["수주"]},
        "performance": {"sample_size": 30, "hit_rate_10x": 0.22, "false_positive_rate": 0.15},
    }

    confidence, breakdown = _score(rule, ["bcr_at_signal", "keywords"])

    assert confidence > 0.55
    assert breakdown["performance_score"] > 0
    assert breakdown["performance_detail"]["sample_size"] == 30


def test_insufficient_performance_history_does_not_overfit():
    rule = {
        "category": "수주잔고_선행",
        "conditions": {"bcr_at_signal": 1.5},
        "performance": {"sample_size": 2, "hit_rate_10x": 1.0},
    }

    _, breakdown = _score(rule, ["bcr_at_signal"])

    assert breakdown["performance_score"] == 0
    assert breakdown["performance_detail"]["status"] == "insufficient_history"


def test_refutation_penalties_reduce_confidence():
    rule = {
        "category": "빅테크_파트너",
        "conditions": {"keywords": ["전략적 투자"], "amount_threshold_billions": 100},
    }

    clean, _ = _score(rule, ["keywords", "amount_threshold_billions"])
    penalized, breakdown = _score(
        rule,
        ["keywords", "amount_threshold_billions"],
        {"share_count_yoy_pct": 35, "debt_ratio": 320},
    )

    assert penalized < clean
    assert breakdown["refutation_detail"]["dilution"] < 0
    assert breakdown["refutation_detail"]["debt_ratio"] < 0
