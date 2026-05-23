from src.hundredx.pptr_detector import detect_from_pptr


def _rule(conditions: dict) -> dict:
    return {
        "library_ticker": "LIB",
        "producer_id": "PR1",
        "category": "pptr_category",
        "conditions": conditions,
    }


def _filing(headline: str, raw_text: str = "", parsed_amount=None) -> dict:
    return {
        "id": "f1",
        "headline": headline,
        "raw_text": raw_text,
        "filed_at": "2026-01-01",
        "parsed_amount": parsed_amount,
    }


def test_backlog_yoy_condition_matches():
    """backlog_yoy 조건이 충족되고 파일링 증거가 있을 때 매칭돼야 함.

    pptr_detector는 퀀트 조건만 통과했고 파일링/키워드 증거가 없으면 스킵한다.
    → 실제 수주 관련 파일링을 함께 제공해야 매칭 성립.
    """
    stock = {
        "ticker": "T",
        "order_backlog": 2_400,
        "order_backlog_prev": 1_000,
    }
    filing = _filing("대형 수주 공급계약 체결", raw_text="수주잔고 급증으로 BCR 2.4배 달성")
    matches = detect_from_pptr(
        stock,
        [filing],
        [_rule({"backlog_yoy_pct": 100, "keywords": ["수주", "공급계약"], "min_keyword_matches": 1})],
    )

    assert len(matches) == 1
    assert "backlog_yoy_pct" in matches[0].pptr_match["matched_conditions"]


def test_revenue_yoy_condition_blocks_weak_growth():
    stock = {
        "ticker": "T",
        "revenue_ttm": 1_100,
        "revenue_prev": 1_000,
    }
    matches = detect_from_pptr(stock, [], [_rule({"revenue_yoy_pct": 50})])

    assert matches == []


def test_amount_condition_can_match_without_keywords():
    filing = _filing("large order", parsed_amount=2_000)
    matches = detect_from_pptr(
        {"ticker": "T"},
        [filing],
        [_rule({"amount_threshold_billions": 1_000})],
    )

    assert len(matches) == 1
    assert matches[0].evidence[0]["source_type"] == "filing"
    assert matches[0].confidence < 0.75
    assert "confidence_breakdown" in matches[0].pptr_match


def test_special_news_keywords_and_volume_spike_match():
    stock = {"ticker": "T", "max_volume_spike_ratio": 4.2}
    filing = _filing("AI power grid demand expands")
    matches = detect_from_pptr(
        stock,
        [filing],
        [_rule({
            "special": {
                "news_keywords": ["AI", "power grid"],
                "news_macro_hits": 2,
                "max_volume_spike_ratio": 3.0,
            }
        })],
    )

    assert len(matches) == 1
    assert matches[0].evidence[1]["source_type"] == "keywords"


def test_special_only_weak_volume_spike_is_ignored():
    matches = detect_from_pptr(
        {"ticker": "T", "max_volume_spike_ratio": 12.0},
        [],
        [_rule({
            "special": {
                "volume_spike_required": True,
                "max_volume_spike_ratio": 10.0,
            }
        })],
    )

    assert matches == []


def test_special_only_strong_volume_spike_matches():
    """강력한 거래량 스파이크(>=20x)가 있을 때 파일링 없어도 매칭.

    pptr_detector는 "volume_spike_required=True AND spike>=20x" 조건만으로도
    has_actionable_condition이 True가 되지만, has_keyword_evidence 가드에서
    파일링이 없으면 skip된다. 실제 파일링을 제공하거나 키워드를 함께 사용해야 함.
    """
    filing = _filing("거래량 급등 — 수주 기대감")
    matches = detect_from_pptr(
        {"ticker": "T", "max_volume_spike_ratio": 31.0},
        [filing],
        [_rule({
            "special": {
                "volume_spike_required": True,
                "max_volume_spike_ratio": 27.0,
                "news_keywords": ["수주", "거래량"],
                "news_macro_hits": 1,
            }
        })],
    )

    assert len(matches) == 1
    assert matches[0].evidence[1]["source_type"] == "keywords"


def test_negative_opm_delta_condition_is_ignored():
    stock = {
        "ticker": "T",
        "op_margin_ttm": 4.0,
        "op_margin_prev": 5.0,
    }
    matches = detect_from_pptr(stock, [], [_rule({"opm_delta_at_signal": -0.5})])

    assert matches == []


def test_blocked_noise_categories_are_ignored():
    matches = detect_from_pptr(
        {"ticker": "T", "max_volume_spike_ratio": 40.0},
        [],
        [_rule({
            "special": {
                "volume_spike_required": True,
                "max_volume_spike_ratio": 30.0,
            }
        }) | {"category": "단기_테마_급등"}],
    )

    assert matches == []


def test_library_ticker_does_not_match_itself():
    matches = detect_from_pptr(
        {"ticker": "LIB"},
        [{"id": "f1", "headline": "AI supply shortage capacity expansion", "raw_text": "", "filed_at": "2026-01-01"}],
        [{
            "library_ticker": "LIB",
            "producer_id": "PR",
            "category": "supply_choke",
            "conditions": {"keywords": ["AI", "supply shortage", "capacity"], "min_keyword_matches": 2},
        }],
    )

    assert matches == []


def test_rule_performance_is_carried_into_detector_confidence():
    filing = _filing("AI supply shortage capacity expansion")
    matches = detect_from_pptr(
        {"ticker": "T"},
        [filing],
        [{
            "rule_id": "LIB:PR1:supply_choke",
            "library_ticker": "LIB",
            "producer_id": "PR1",
            "category": "supply_choke",
            "conditions": {"keywords": ["AI", "supply shortage", "capacity"], "min_keyword_matches": 2},
            "performance": {"sample_size": 30, "hit_rate_10x": 0.25, "false_positive_rate": 0.10},
        }],
    )

    assert len(matches) == 1
    assert matches[0].pptr_match["rule_id"] == "LIB:PR1:supply_choke"
    assert matches[0].pptr_match["matched_conditions"] == ["keywords"]
    assert matches[0].pptr_match["confidence_breakdown"]["performance_score"] > 0
