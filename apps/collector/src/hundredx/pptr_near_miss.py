"""PPTR near-miss mining.

Near misses are not alerts. They are learning material: partial rule firings
that can later prove whether a strict PPTR rule should be loosened, split, or
retired.
"""
from __future__ import annotations

from .keywords import _extract_amount_krw
from .pptr_detector import BLOCKED_PPTR_CATEGORIES, _kw_hit

MIN_NEAR_MISS_SCORE = 0.40


def _safe_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _combined_text(filings: list[dict]) -> str:
    return " ".join(
        (f.get("raw_text") or "") + " " + (f.get("headline") or "")
        for f in filings
    )


def _best_amount(filings: list[dict]) -> float | None:
    best = None
    for filing in filings:
        text = (filing.get("raw_text") or "") + " " + (filing.get("headline") or "")
        amount = _extract_amount_krw(text)
        if amount is None:
            amount = _safe_float(filing.get("parsed_amount"))
        if amount is not None and (best is None or amount > best):
            best = amount
    return best


def _bcr(stock_data: dict) -> float | None:
    backlog = stock_data.get("order_backlog")
    revenue = stock_data.get("revenue_ttm") or stock_data.get("revenue")
    if backlog is None or not revenue or revenue <= 0:
        return None
    return backlog / revenue


def analyze_pptr_near_misses(
    stock_data: dict,
    filings: list[dict],
    library_pptr_rules: list[dict],
    max_per_ticker: int = 3,
) -> list[dict]:
    """Return partial PPTR matches worth tracking as learning data."""
    ticker = stock_data.get("ticker", "")
    sector_tag = stock_data.get("sector_tag")
    text = _combined_text(filings)
    best_amount = _best_amount(filings)

    candidates: list[dict] = []
    for rule in library_pptr_rules:
        if rule.get("library_ticker") and ticker == rule.get("library_ticker"):
            continue
        category = rule.get("category")
        if not category or category in BLOCKED_PPTR_CATEGORIES:
            continue
        conditions = rule.get("conditions") or {}
        checks = []

        req_sector = conditions.get("sector_required")
        if req_sector:
            checks.append(("sector_required", req_sector == sector_tag, {"required": req_sector, "actual": sector_tag}))

        keywords = conditions.get("keywords") or []
        if keywords:
            hits = _kw_hit(text, keywords)
            min_kw = int(conditions.get("min_keyword_matches") or 1)
            checks.append(("keywords", len(hits) >= min_kw, {
                "hits": hits[:12],
                "hit_count": len(hits),
                "min_required": min_kw,
                "total_keywords": len(keywords),
            }))

        amount_min = conditions.get("amount_threshold_billions")
        if amount_min is not None:
            checks.append(("amount_threshold_billions", best_amount is not None and best_amount >= amount_min, {
                "required": amount_min,
                "actual": best_amount,
            }))

        bcr_min = conditions.get("bcr_at_signal")
        if bcr_min is not None:
            actual_bcr = _bcr(stock_data)
            checks.append(("bcr_at_signal", actual_bcr is not None and actual_bcr >= bcr_min, {
                "required": bcr_min,
                "actual": round(actual_bcr, 3) if actual_bcr is not None else None,
            }))

        opm_min = conditions.get("opm_at_signal")
        if opm_min is not None:
            opm = _safe_float(stock_data.get("op_margin_ttm"))
            checks.append(("opm_at_signal", opm is not None and opm >= opm_min, {
                "required": opm_min,
                "actual": opm,
            }))

        opm_delta_min = conditions.get("opm_delta_at_signal")
        if opm_delta_min is not None:
            opm = _safe_float(stock_data.get("op_margin_ttm"))
            opm_prev = _safe_float(stock_data.get("op_margin_prev"))
            delta = opm - opm_prev if opm is not None and opm_prev is not None else None
            checks.append(("opm_delta_at_signal", delta is not None and delta >= opm_delta_min, {
                "required": opm_delta_min,
                "actual": round(delta, 3) if delta is not None else None,
            }))

        if not checks:
            continue

        matched = [name for name, ok, _ in checks if ok]
        missing = [name for name, ok, _ in checks if not ok]
        if not matched or not missing:
            continue
        if not any(name in matched for name in ("keywords", "amount_threshold_billions", "bcr_at_signal")):
            continue

        score = len(matched) / len(checks)
        if score < MIN_NEAR_MISS_SCORE:
            continue

        candidates.append({
            "rule_id": rule.get("rule_id"),
            "library_ticker": rule.get("library_ticker"),
            "ticker": ticker,
            "category": category,
            "near_miss_score": round(score, 3),
            "matched_conditions": matched,
            "missing_conditions": missing,
            "details": {name: detail for name, _, detail in checks},
        })

    candidates.sort(key=lambda row: row["near_miss_score"], reverse=True)
    return candidates[:max_per_ticker]
