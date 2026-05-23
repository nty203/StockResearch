from src.hundredx.pptr_near_miss import analyze_pptr_near_misses


def test_near_miss_tracks_partial_rule_firing():
    near = analyze_pptr_near_misses(
        {"ticker": "T", "sector_tag": "전력기기", "order_backlog": 900, "revenue_ttm": 1000},
        [{"headline": "AI data center transformer demand creates long lead time", "raw_text": ""}],
        [{
            "rule_id": "R1",
            "library_ticker": "LIB",
            "category": "공급_병목",
            "conditions": {
                "sector_required": "전력기기",
                "keywords": ["AI", "transformer", "lead time", "shortage"],
                "min_keyword_matches": 3,
                "bcr_at_signal": 1.5,
            },
        }],
    )

    assert len(near) == 1
    assert near[0]["near_miss_score"] == 0.667
    assert "bcr_at_signal" in near[0]["missing_conditions"]


def test_near_miss_requires_specific_signal_not_only_sector_or_opm():
    near = analyze_pptr_near_misses(
        {"ticker": "T", "sector_tag": "방산", "op_margin_ttm": 6.0},
        [],
        [{
            "rule_id": "R1",
            "library_ticker": "LIB",
            "category": "수주잔고_선행",
            "conditions": {
                "sector_required": "방산",
                "opm_at_signal": 4.0,
                "keywords": ["K-9", "수주"],
                "min_keyword_matches": 1,
                "bcr_at_signal": 1.5,
            },
        }],
    )

    assert near == []


def test_near_miss_ignores_library_ticker_itself():
    near = analyze_pptr_near_misses(
        {"ticker": "LIB", "sector_tag": "전력기기", "order_backlog": 900, "revenue_ttm": 1000},
        [{"headline": "AI transformer lead time", "raw_text": ""}],
        [{
            "rule_id": "R1",
            "library_ticker": "LIB",
            "category": "공급_병목",
            "conditions": {"keywords": ["AI", "transformer", "lead time"], "min_keyword_matches": 2},
        }],
    )

    assert near == []


def test_near_miss_ignores_noise_categories():
    near = analyze_pptr_near_misses(
        {"ticker": "T", "max_volume_spike_ratio": 40},
        [],
        [{
            "rule_id": "R1",
            "library_ticker": "LIB",
            "category": "단기_테마_급등",
            "conditions": {"special": {"volume_spike_required": True, "max_volume_spike_ratio": 30}},
        }],
    )

    assert near == []
