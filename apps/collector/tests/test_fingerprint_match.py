"""Tests for fingerprint matching engine."""
import pytest

from src.hundredx.fingerprint_match import (
    match_against_library_entry,
    best_match_in_category,
    _compute_current_quant,
)


def _filing(headline: str, raw_text: str = "", filed_at: str = "2025-01-01",
            parsed_amount: float | None = None) -> dict:
    return {
        "id": "f1", "ticker": "T", "headline": headline, "raw_text": raw_text,
        "filed_at": filed_at, "parsed_amount": parsed_amount,
    }


def _hanwha_lib_entry() -> dict:
    """한화에어로스페이스 fingerprint (수주잔고_선행)."""
    return {
        "ticker": "012450",
        "category": "수주잔고_선행",
        "rise_start_date": "2022-07-01",
        "pre_rise_signals": {
            "quant": {"bcr_at_signal": 2.8, "backlog_yoy_pct": 115, "opm_at_signal": 2.8, "opm_prev": 1.2},
            "keywords": ["폴란드", "K-9", "K-2", "FA-50", "NATO", "방산", "수출", "조원"],
            "min_keyword_matches": 3,
            "amount_threshold_billions": 9000,
            "sector_required": "방산",
        },
    }


class TestComputeCurrentQuant:
    def test_bcr_computed(self):
        out = _compute_current_quant({
            "order_backlog": 2_800, "revenue_ttm": 1_000,
        })
        assert out["bcr_at_signal"] == 2.8

    def test_backlog_yoy(self):
        out = _compute_current_quant({
            "order_backlog": 2_000, "order_backlog_prev": 1_000,
        })
        assert out["backlog_yoy_pct"] == 100.0

    def test_opm_delta(self):
        out = _compute_current_quant({"op_margin_ttm": 8.0, "op_margin_prev": 2.0})
        assert out["opm_delta"] == 6.0

    def test_revenue_growth(self):
        out = _compute_current_quant({"revenue_ttm": 1500, "revenue_prev": 1000})
        assert out["revenue_growth_yoy"] == 50.0


class TestFingerprintMatch:
    def test_perfect_match(self):
        """Stock with exactly 한화에어로 fingerprint values should score very high."""
        stock = {
            "ticker": "TEST", "sector_tag": "방산",
            "order_backlog": 2_800, "revenue_ttm": 1_000,
            "order_backlog_prev": 1_000,  # YoY = 180%
            "op_margin_ttm": 2.8, "op_margin_prev": 1.2,
        }
        filings = [_filing("폴란드 K-9 자주포 9000억 수출 NATO 방산 K-2",
                           parsed_amount=9000)]
        match = match_against_library_entry(stock, filings, _hanwha_lib_entry())
        assert match.score >= 0.85
        assert any("quant" in d for d in match.matched_dims)
        assert any("sector" in d for d in match.matched_dims)
        assert any("amount" in d for d in match.matched_dims)
        # Details dict contains breakdown per dimension
        assert "quant" in match.details
        assert "keywords" in match.details

    def test_partial_match_missing_quant(self):
        """No backlog data → quant misses, but keywords + sector match."""
        stock = {"ticker": "T", "sector_tag": "방산"}
        filings = [_filing("폴란드 K-9 NATO 방산 수출")]
        match = match_against_library_entry(stock, filings, _hanwha_lib_entry())
        assert 0.3 < match.score < 0.85
        # All quant fields should be in missing
        missing_quant = [d for d in match.missing_dims if d.startswith("quant.")]
        assert len(missing_quant) >= 3

    def test_wrong_sector_lowers_score(self):
        """Same financial pattern but wrong sector should score lower."""
        stock = {
            "ticker": "T", "sector_tag": "IT서비스",  # not 방산
            "order_backlog": 2_800, "revenue_ttm": 1_000,
            "order_backlog_prev": 1_000,
            "op_margin_ttm": 2.8, "op_margin_prev": 1.2,
        }
        filings = [_filing("폴란드 K-9 NATO 방산 수출 9000억", parsed_amount=9000)]
        match_correct_sector = match_against_library_entry(
            {**stock, "sector_tag": "방산"}, filings, _hanwha_lib_entry()
        )
        match_wrong_sector = match_against_library_entry(stock, filings, _hanwha_lib_entry())
        assert match_correct_sector.score > match_wrong_sector.score

    def test_no_keyword_hits(self):
        """Filings with no matching keywords → keyword dim fails."""
        stock = {"ticker": "T", "sector_tag": "방산"}
        filings = [_filing("일반 영업 공시 분기실적")]
        match = match_against_library_entry(stock, filings, _hanwha_lib_entry())
        kw_missing = [d for d in match.missing_dims if d.startswith("keywords")]
        assert len(kw_missing) == 1


class TestBestMatchInCategory:
    def test_picks_highest_score(self):
        """Multiple library entries → returns the one with highest fingerprint similarity."""
        lib = [
            _hanwha_lib_entry(),
            {  # different stock, different category
                "ticker": "267260", "category": "수주잔고_선행",
                "rise_start_date": "2023-01-01",
                "pre_rise_signals": {
                    "quant": {"bcr_at_signal": 1.4, "backlog_yoy_pct": 100},
                    "keywords": ["HVDC", "변압기", "미국"],
                    "min_keyword_matches": 2,
                    "sector_required": "전력기기",
                },
            },
        ]
        # Stock that looks like 한화에어로
        stock = {
            "ticker": "T", "sector_tag": "방산",
            "order_backlog": 2_500, "revenue_ttm": 1_000,
            "order_backlog_prev": 1_000,
        }
        filings = [_filing("폴란드 K-9 NATO 방산 수출 9000억", parsed_amount=9000)]
        match = best_match_in_category(stock, filings, lib, "수주잔고_선행")
        assert match is not None
        assert match.library_ticker == "012450"

    def test_no_candidates_returns_none(self):
        lib = [_hanwha_lib_entry()]  # only 수주잔고_선행
        stock = {"ticker": "T"}
        match = best_match_in_category(stock, [], lib, "임상_파이프라인")
        assert match is None
