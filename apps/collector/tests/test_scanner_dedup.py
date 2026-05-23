"""Tests for category deduplication logic in scanner.py."""
import pytest
from src.hundredx.scanner import _deduplicate_categories
from src.hundredx.models import CategoryMatch


def _match(ticker: str, category: str, confidence: float) -> CategoryMatch:
    return CategoryMatch(ticker=ticker, category=category, confidence=confidence)


class TestDeduplicateCategories:
    def test_empty_list_returns_empty(self):
        assert _deduplicate_categories([]) == []

    def test_single_match_unchanged(self):
        m = _match("A", "수주잔고_선행", 0.80)
        result = _deduplicate_categories([m])
        assert len(result) == 1
        assert result[0].ticker == "A"

    def test_single_ticker_two_categories_keeps_best(self):
        """When one ticker fires two non-always-keep categories, keep the higher confidence."""
        m1 = _match("A", "수주잔고_선행", 0.75)
        m2 = _match("A", "공급_병목", 0.85)
        result = _deduplicate_categories([m1, m2])
        assert len(result) == 1
        assert result[0].category == "공급_병목"
        assert result[0].confidence == 0.85

    def test_single_ticker_six_categories_deduped(self):
        """The 373220-style false positive: 6 non-clinical categories → 2 kept.

        수익성_급전환 is always-keep, so it survives.
        빅테크_파트너 has highest category priority among the rest → also kept.
        Total: 2 instead of 6.
        """
        categories = [
            ("수주잔고_선행", 0.750),
            ("수익성_급전환", 0.750),  # always-keep
            ("빅테크_파트너", 0.750),
            ("플랫폼_독점", 0.750),
            ("정책_수혜", 0.750),
            ("공급_병목", 0.750),
        ]
        matches = [_match("373220", cat, conf) for cat, conf in categories]
        result = _deduplicate_categories(matches)
        cats = {m.category for m in result}
        # 수익성_급전환 (always-keep) + 빅테크_파트너 (best by priority)
        assert "수익성_급전환" in cats
        assert "빅테크_파트너" in cats
        # The other 4 categories should be removed
        assert "수주잔고_선행" not in cats
        assert "플랫폼_독점" not in cats
        assert "정책_수혜" not in cats
        assert "공급_병목" not in cats
        assert len(result) == 2

    def test_always_keep_clinical_preserved_alongside_best(self):
        """임상_파이프라인 is always-keep: preserved even if another category has higher conf."""
        m_clinical = _match("B", "임상_파이프라인", 0.72)
        m_backlog = _match("B", "수주잔고_선행", 0.90)
        m_supply = _match("B", "공급_병목", 0.85)
        result = _deduplicate_categories([m_clinical, m_backlog, m_supply])
        # clinical is always kept, plus the best non-always-keep (수주잔고_선행 @ 0.90)
        cats = {m.category for m in result}
        assert "임상_파이프라인" in cats
        assert "수주잔고_선행" in cats
        assert "공급_병목" not in cats
        assert len(result) == 2

    def test_always_keep_profit_preserved(self):
        """수익성_급전환 is always-keep."""
        m_profit = _match("C", "수익성_급전환", 0.75)
        m_supply = _match("C", "공급_병목", 0.80)
        result = _deduplicate_categories([m_profit, m_supply])
        cats = {m.category for m in result}
        assert "수익성_급전환" in cats
        assert "공급_병목" in cats  # best non-always-keep
        assert len(result) == 2

    def test_multiple_tickers_independent(self):
        """Dedup is per-ticker; different tickers are independent."""
        m1 = _match("A", "공급_병목", 0.85)
        m2 = _match("A", "수주잔고_선행", 0.75)
        m3 = _match("B", "플랫폼_독점", 0.78)
        m4 = _match("B", "정책_수혜", 0.72)
        result = _deduplicate_categories([m1, m2, m3, m4])
        by_ticker = {m.ticker: m for m in result}
        assert by_ticker["A"].category == "공급_병목"  # higher conf
        assert by_ticker["B"].category == "플랫폼_독점"  # higher conf
        assert len(result) == 2

    def test_ties_broken_by_category_priority(self):
        """Equal confidence → higher category priority wins."""
        # Both 0.75; 빅테크_파트너(7) > 공급_병목(3)
        m1 = _match("D", "공급_병목", 0.75)
        m2 = _match("D", "빅테크_파트너", 0.75)
        result = _deduplicate_categories([m1, m2])
        assert len(result) == 1
        assert result[0].category == "빅테크_파트너"

    def test_preserve_all_when_only_always_keep(self):
        """If a ticker only has always-keep categories, all are preserved."""
        m1 = _match("E", "임상_파이프라인", 0.72)
        m2 = _match("E", "수익성_급전환", 0.80)
        result = _deduplicate_categories([m1, m2])
        # Both are always-keep → both preserved
        cats = {m.category for m in result}
        assert "임상_파이프라인" in cats
        assert "수익성_급전환" in cats
        assert len(result) == 2
