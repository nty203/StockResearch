"""Fingerprint matching engine — compares current stock signals to library precedent.

Concept: each library stock's pre_rise_signals JSONB encodes the SHAPE of signals
that preceded its 100x rise. This engine takes a current stock's data and computes
how similar its signal shape is to each library stock in the same category.

Returns a score (0-1) and a breakdown of matched/missing dimensions, so the UI
can show "현재 종목 → 한화에어로 2021Q3 패턴 76% 일치 (BCR ✓ OPM ✓ 키워드 5/6 ✓)"

Match dimensions:
- quant       : numeric thresholds (BCR, OPM gap, revenue growth) — up to 4 fields
- keywords    : keyword set match (matched_count / total) — uses min_keyword_matches gate
- sector      : exact sector_tag match (binary)
- amount      : single filing amount above amount_threshold (binary, optional)
- special     : structural patterns (callopt, vertical_complete, etc.) — binary each

Final score = weighted average of available dimensions (each weight = 1.0).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FingerprintMatch:
    library_ticker: str
    library_category: str
    score: float                              # 0.0 – 1.0
    matched_dims: list[str] = field(default_factory=list)
    missing_dims: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


# Tolerance ratios for quantitative match — current value within X% of library
_QUANT_TOLERANCE = 0.30   # 30% tolerance band

_QUANT_FIELD_TO_STOCK_KEY = {
    "bcr_at_signal":        "bcr_at_signal",        # current_bcr (computed by detector)
    "backlog_yoy_pct":      "backlog_yoy_pct",
    "opm_at_signal":        "op_margin_ttm",
    "opm_prev":             "op_margin_prev",
    "opm_delta_at_signal":  "opm_delta",            # computed = ttm - prev
    "revenue_growth_yoy":   "revenue_growth_yoy",   # computed = (ttm - prev) / prev
    # Quality/efficiency metrics (Bessembinder 2018, CAFE 2025, Mayer 2015)
    "roic_at_signal":       "roic",                 # Return on Invested Capital
    "fcf_margin_at_signal": "fcf_margin",           # FCF / Revenue TTM (%)
    "debt_ratio_at_signal": "debt_ratio",           # Total Liabilities / Total Assets (%)
    # Piotroski / Sloan / Novy-Marx quality metrics
    "gp_to_assets_at_signal":   "gp_to_assets",     # Novy-Marx GP/A
    "accruals_ratio_at_signal": "accruals_ratio",   # Sloan (NI - CFO) / Avg Assets
    "f_score_at_signal":        "f_score",          # Piotroski 0-9
    # Revenue acceleration (Asness 2013, multibagger leading indicator)
    "revenue_qoq_acceleration_at_signal": "revenue_qoq_acceleration",
    # Market cap at signal time (Mayer 100 Baggers: small-cap = higher multibagger probability)
    "market_cap_at_signal": "market_cap",
}


def _compute_current_quant(stock_data: dict) -> dict[str, float]:
    """Derive numeric signals from raw stock_data for quant comparison."""
    out: dict[str, float] = {}

    backlog = stock_data.get("order_backlog")
    backlog_prev = stock_data.get("order_backlog_prev")
    revenue_ttm = stock_data.get("revenue_ttm")
    revenue_prev = stock_data.get("revenue_prev")
    opm_ttm = stock_data.get("op_margin_ttm")
    opm_prev = stock_data.get("op_margin_prev")

    if backlog is not None and revenue_ttm and revenue_ttm > 0:
        out["bcr_at_signal"] = backlog / revenue_ttm
    if backlog is not None and backlog_prev and backlog_prev > 0:
        out["backlog_yoy_pct"] = (backlog - backlog_prev) / backlog_prev * 100
    if opm_ttm is not None:
        out["op_margin_ttm"] = opm_ttm
    if opm_prev is not None:
        out["op_margin_prev"] = opm_prev
    if opm_ttm is not None and opm_prev is not None:
        out["opm_delta"] = opm_ttm - opm_prev
    if revenue_ttm and revenue_prev and revenue_prev > 0:
        out["revenue_growth_yoy"] = (revenue_ttm - revenue_prev) / revenue_prev * 100

    # ── Quality/efficiency metrics (research-backed 100x predictors) ──────────
    # ROIC (Return on Invested Capital): quality moat indicator.
    # Phelps "100 to 1": ROIC > 9%; Greenblatt: ROIC > 15%.
    roic = stock_data.get("roic")
    if roic is not None:
        out["roic"] = roic

    # FCF margin = FCF / Revenue (%). CAFE Working Paper 2025: FCF yield is the
    # strongest single predictor of multibagger status.
    # We use FCF/Revenue (margin) rather than FCF/MarketCap (yield) because
    # it normalises across company sizes and doesn't need real-time market cap.
    fcf = stock_data.get("fcf")
    if fcf is not None and revenue_ttm and revenue_ttm > 0:
        out["fcf_margin"] = fcf / revenue_ttm * 100  # in %

    # Debt ratio (%). Low debt = financial runway for growth.
    debt_ratio = stock_data.get("debt_ratio")
    if debt_ratio is not None:
        out["debt_ratio"] = debt_ratio

    # ── Quality metrics (Piotroski/Sloan/Novy-Marx) ───────────────────────────
    gp_to_assets = stock_data.get("gp_to_assets")
    if gp_to_assets is not None:
        out["gp_to_assets"] = gp_to_assets
    accruals = stock_data.get("accruals_ratio")
    if accruals is not None:
        out["accruals_ratio"] = accruals
    f_score = stock_data.get("f_score")
    if f_score is not None:
        out["f_score"] = f_score

    rev_qoq_acc = stock_data.get("revenue_qoq_acceleration")
    if rev_qoq_acc is not None:
        out["revenue_qoq_acceleration"] = rev_qoq_acc

    return out


def _quant_match(library_quant: dict, current_quant: dict) -> tuple[list[str], list[str], dict]:
    """For each library quant threshold, check if current value is within tolerance."""
    matched: list[str] = []
    missing: list[str] = []
    details: dict = {}

    for lib_field, lib_value in library_quant.items():
        stock_key = _QUANT_FIELD_TO_STOCK_KEY.get(lib_field)
        if stock_key is None:
            continue
        current_value = current_quant.get(stock_key)
        if current_value is None:
            missing.append(lib_field)
            continue

        # Direction-aware match:
        # - For ratios (BCR, OPM, growth, ROIC, FCF margin) higher than library is GOOD
        # - For prev OPM (low-base inflection) lower or equal is OK
        # - For debt_ratio lower is better (less debt = more runway)
        if lib_field in ("opm_prev",):
            # low-base requirement: current opm_prev should be <= library_opm_prev * (1 + tolerance)
            ok = current_value <= lib_value * (1 + _QUANT_TOLERANCE)
        elif lib_field in ("debt_ratio_at_signal", "accruals_ratio_at_signal"):
            # Lower is better. accruals_ratio: negative (CFO>NI) is best;
            # cap upper bound using absolute tolerance for sign-sensitive metric.
            if lib_field == "accruals_ratio_at_signal":
                ok = current_value <= max(lib_value, 0) + _QUANT_TOLERANCE
            else:
                ok = current_value <= lib_value * (1 + _QUANT_TOLERANCE)
        elif lib_field == "f_score_at_signal":
            # F-Score is discrete 0-9; allow ±2 around library value
            ok = current_value >= lib_value - 2
        elif lib_field == "market_cap_at_signal":
            # Lower market cap is better (Mayer 100B). Match if current cap
            # is within 5× of library at-signal cap (i.e. similar scale or smaller).
            ok = current_value <= lib_value * 5
        else:
            ok = current_value >= lib_value * (1 - _QUANT_TOLERANCE)

        if ok:
            matched.append(lib_field)
        else:
            missing.append(lib_field)
        details[lib_field] = {"library": lib_value, "current": round(current_value, 3)}

    return matched, missing, details


def _keyword_match(library_kws: list[str], min_matches: int, filings: list[dict]) -> tuple[int, int, list[str]]:
    """Count library keyword hits across all filings text. Returns (hits, threshold, matched_kws)."""
    if not library_kws or not filings:
        return 0, min_matches, []
    combined_text = " ".join(
        ((f.get("raw_text") or "") + " " + (f.get("headline") or "")).lower()
        for f in filings
    )
    matched = [kw for kw in library_kws if kw.lower() in combined_text]
    return len(matched), min_matches, matched


def _amount_match(threshold_billions: float | None, filings: list[dict]) -> bool | None:
    """Check if any filing has parsed_amount >= threshold (billions KRW)."""
    if threshold_billions is None:
        return None  # no requirement
    for f in filings:
        amount = f.get("parsed_amount")
        if amount is not None and amount >= threshold_billions:
            return True
    return False


def match_against_library_entry(
    stock_data: dict,
    filings: list[dict],
    library_entry: dict,
) -> FingerprintMatch:
    """Compute fingerprint similarity between current stock and one library entry.

    library_entry: row from hundredx_library_stocks with pre_rise_signals JSONB.
    """
    pre_signals = library_entry.get("pre_rise_signals") or {}
    library_ticker = library_entry.get("ticker", "?")
    library_category = library_entry.get("category", "?")

    matched_dims: list[str] = []
    missing_dims: list[str] = []
    weighted_score = 0.0
    weight_total = 0.0
    details: dict[str, Any] = {}

    # Quantitative dimension
    library_quant = pre_signals.get("quant") or {}
    if library_quant:
        current_quant = _compute_current_quant(stock_data)
        q_matched, q_missing, q_details = _quant_match(library_quant, current_quant)
        total_quant = len(library_quant)
        if total_quant > 0:
            quant_score = len(q_matched) / total_quant
            weighted_score += quant_score
            weight_total += 1.0
            details["quant"] = q_details
            for f in q_matched: matched_dims.append(f"quant.{f}")
            for f in q_missing: missing_dims.append(f"quant.{f}")

    # Keyword dimension
    library_kws = pre_signals.get("keywords") or []
    if library_kws:
        min_matches = pre_signals.get("min_keyword_matches", 1)
        kw_hits, kw_min, kw_list = _keyword_match(library_kws, min_matches, filings)
        kw_score = min(1.0, kw_hits / max(1, len(library_kws)))
        weighted_score += kw_score
        weight_total += 1.0
        details["keywords"] = {
            "library": library_kws,
            "matched": kw_list,
            "hit_count": kw_hits,
            "min_required": kw_min,
            "passed_threshold": kw_hits >= kw_min,
        }
        if kw_hits >= kw_min:
            matched_dims.append(f"keywords({kw_hits}/{len(library_kws)})")
        else:
            missing_dims.append(f"keywords({kw_hits}/{len(library_kws)}_below_{kw_min})")

    # Sector dimension
    sector_required = pre_signals.get("sector_required")
    if sector_required:
        current_sector = stock_data.get("sector_tag")
        if current_sector == sector_required:
            matched_dims.append(f"sector={sector_required}")
            weighted_score += 1.0
        else:
            missing_dims.append(f"sector(want={sector_required},got={current_sector})")
            weighted_score += 0.0
        weight_total += 1.0
        details["sector"] = {"library": sector_required, "current": current_sector}

    # Amount dimension
    amount_threshold = pre_signals.get("amount_threshold_billions")
    if amount_threshold is not None:
        ok = _amount_match(amount_threshold, filings)
        if ok:
            matched_dims.append(f"amount>={amount_threshold}억")
            weighted_score += 1.0
        else:
            missing_dims.append(f"amount<{amount_threshold}억")
            weighted_score += 0.0
        weight_total += 1.0
        details["amount"] = {"library_threshold": amount_threshold, "matched": bool(ok)}

    final_score = (weighted_score / weight_total) if weight_total > 0 else 0.0

    return FingerprintMatch(
        library_ticker=library_ticker,
        library_category=library_category,
        score=round(final_score, 3),
        matched_dims=matched_dims,
        missing_dims=missing_dims,
        details=details,
    )


def best_match_in_category(
    stock_data: dict,
    filings: list[dict],
    library_entries: list[dict],
    category: str,
) -> FingerprintMatch | None:
    """Pick the library entry in `category` with highest fingerprint similarity to current."""
    candidates = [e for e in library_entries if e.get("category") == category]
    if not candidates:
        return None
    matches = [match_against_library_entry(stock_data, filings, e) for e in candidates]
    return max(matches, key=lambda m: m.score)
