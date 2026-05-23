from src.news_rss import _build_mention_map, _find_ticker_mentions


def test_find_ticker_mentions_by_company_name():
    stocks = [
        {"ticker": "042700", "name_kr": "한미반도체", "name_en": "Hanmi Semiconductor"},
        {"ticker": "108490", "name_kr": "로보티즈", "name_en": "Robotis"},
    ]
    mention_map = _build_mention_map(stocks)

    hits = _find_ticker_mentions(
        "한미반도체가 HBM 장비 수주를 확대했다.",
        {"042700", "108490"},
        mention_map,
    )

    assert hits == ["042700"]


def test_find_ticker_mentions_still_matches_numeric_code():
    hits = _find_ticker_mentions("042700 신규 공급 계약", {"042700"}, {})

    assert hits == ["042700"]
