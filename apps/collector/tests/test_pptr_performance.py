from src.hundredx.pptr_performance import summarize_returns


def test_summarize_returns_tracks_multibagger_hit_rates():
    summary = summarize_returns([0.8, 1.2, 2.5, 12.0])

    assert summary["sample_size"] == 4
    assert summary["hit_rate_2x"] == 0.5
    assert summary["hit_rate_10x"] == 0.25
    assert summary["hit_rate_30x"] == 0.0
    assert summary["false_positive_rate"] == 0.25


def test_summarize_returns_handles_empty_samples():
    summary = summarize_returns([])

    assert summary["sample_size"] == 0
    assert summary["hit_rate_10x"] is None
    assert summary["false_positive_rate"] is None
