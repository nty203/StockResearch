from src.hundredx.pptr_detector import detect_from_pptr
from src.hundredx.pptr_engine import generate_pptr


def test_generate_pptr_mines_trigger_signals_into_detector_rule():
    pptr = generate_pptr({
        "ticker": "T",
        "category": "supply_choke",
        "peak_multiplier": 20,
        "rise_start_date": "2024-01-01",
        "pre_rise_signals": {},
        "triggers": [{
            "seq": 1,
            "name": "AI supply shortage",
            "weight": 1.2,
            "signals": {
                "keywords": ["AI", "supply shortage", "capacity"],
                "quant": {"bcr_at_signal": 1.5},
                "amount": 100,
            },
        }],
    })

    rule = pptr["resolutions"][0]["detector_rule"]["conditions"]

    assert rule["keywords"] == ["AI", "supply shortage", "capacity"]
    assert rule["min_keyword_matches"] == 2
    assert rule["bcr_at_signal"] == 1.5
    assert rule["amount_threshold_billions"] == 100.0


def test_detect_from_pptr_skips_empty_or_unsupported_conditions():
    matches = detect_from_pptr(
        {"ticker": "T"},
        [],
        [
            {"library_ticker": "LIB1", "producer_id": "PR1", "category": "cat", "conditions": {}},
            {"library_ticker": "LIB2", "producer_id": "PR2", "category": "cat", "conditions": {"special": {"volume_spike_required": True}}},
        ],
    )

    assert matches == []


def test_detect_from_pptr_matches_supported_trigger_keywords():
    matches = detect_from_pptr(
        {"ticker": "T"},
        [{"id": 1, "headline": "AI supply shortage capacity expansion", "raw_text": "", "filed_at": "2026-01-01"}],
        [{
            "library_ticker": "LIB",
            "producer_id": "PR",
            "category": "supply_choke",
            "conditions": {"keywords": ["AI", "supply shortage", "capacity"], "min_keyword_matches": 2},
        }],
    )

    assert len(matches) == 1
    assert matches[0].pptr_match["library_ticker"] == "LIB"
