from src.hundredx.price_performance import (
    compute_since_date_performance,
    compute_window_performance,
)


def test_window_performance_uses_window_low_as_baseline():
    perf = compute_window_performance([
        ("2023-01-02", 150.0),
        ("2023-10-31", 100.0),
        ("2026-05-07", 1000.0),
        ("2026-05-22", 900.0),
    ])

    assert perf is not None
    assert perf.baseline_date == "2023-10-31"
    assert perf.current_multiplier == 9.0
    assert perf.current_return_pct == 800.0
    assert perf.peak_multiplier == 10.0
    assert perf.peak_return_pct == 900.0


def test_since_date_performance_uses_first_trading_day_near_target():
    perf = compute_since_date_performance([
        ("2023-01-02", 150.0),
        ("2023-01-03", 140.0),
        ("2023-10-31", 100.0),
        ("2026-05-22", 900.0),
    ], "2023-01-01")

    assert perf is not None
    assert perf.baseline_date == "2023-01-02"
    assert perf.current_multiplier == 6.0
    assert perf.current_return_pct == 500.0


def test_window_performance_ignores_invalid_prices():
    perf = compute_window_performance([
        ("2023-01-02", 0.0),
        ("2023-01-03", -1.0),
        ("2023-01-04", 100.0),
        ("2023-01-05", 120.0),
    ])

    assert perf is not None
    assert perf.baseline_close == 100.0
    assert perf.current_multiplier == 1.2
