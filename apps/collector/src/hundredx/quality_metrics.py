"""Quality / efficiency metrics — Piotroski F-Score, Sloan accruals, Novy-Marx GP/A.

Inputs: a list of quarterly financial records (descending by fq), each having
fields: revenue, op_income, net_income, cfo, total_assets, total_equity,
total_liab, gross_profit, shares_out.

Outputs: scalar metrics that downstream fingerprint matching consumes.

Why per-quarter (TTM aggregated) rather than annual:
  Multibagger inflection often happens mid-year; waiting for fiscal-year close
  loses 6-9 months of signal. We sum 4 trailing quarters for flow items
  (revenue, NI, CFO, gross_profit) and take the latest balance for stock items
  (total_assets/equity/liab, shares_out).

References:
  - Piotroski 2000: F-Score 9-point checklist separates value winners
  - Sloan 1996: high accruals predict future underperformance (NI - CFO mismatch)
  - Novy-Marx 2013: gross profit / assets dominates ROE for cross-section returns
"""
from __future__ import annotations
from typing import Iterable


def _sum_flow(records: list[dict], key: str, n: int = 4) -> float | None:
    """Sum first n quarters of a flow field. Returns None if no data.

    NOTE: This is naive sum and is INCORRECT for DART cumulative quarterly data
    (Q2=6mo, Q3=9mo, Q4=12mo cumulative). Use ttm_from_cumulative() instead
    for revenue/op_income/net_income/cfo/gross_profit from DART.
    """
    vals = [r.get(key) for r in records[:n] if r.get(key) is not None]
    return sum(vals) if vals else None


def _fq_to_q(fq: str) -> int | None:
    """Extract quarter number from fq string 'YYYYQN'. Returns None if 'YYYYY' (annual)."""
    if not fq or len(fq) < 6:
        return None
    if fq[-2] != "Q":
        return None
    try:
        return int(fq[-1])
    except ValueError:
        return None


def ttm_from_cumulative(records: list[dict], key: str) -> float | None:
    """Compute trailing-12-month value from DART cumulative quarterly reports.

    DART quarterly reports are cumulative within fiscal year:
      Q1=3mo, Q2=6mo cumulative, Q3=9mo cumulative, Q4=12mo (full year) cumulative.

    Algorithm:
      - If latest is Q4: TTM = Q4 (already full year)
      - If latest is QN (N<4): TTM = Q4_prev_year + QN_current - QN_prev_year
        (= Q(N+1..Q4)_prev_year + Q1..QN_current = rolling 12 months)

    Returns None if insufficient data.

    Records must be sorted descending by fq.
    """
    if not records:
        return None
    latest = records[0]
    latest_q = _fq_to_q(latest.get("fq", ""))
    if latest_q is None:
        return None
    latest_val = latest.get(key)
    if latest_val is None:
        return None

    if latest_q == 4:
        return latest_val  # Q4 cumulative = annual TTM

    # Need Q4_prev_year and QN_prev_year (records[4] is same quarter, prior year)
    if len(records) < 5:
        return None
    same_q_prev_year = records[4]
    if _fq_to_q(same_q_prev_year.get("fq", "")) != latest_q:
        return None  # sequence broken
    same_q_prev_val = same_q_prev_year.get(key)
    if same_q_prev_val is None:
        return None

    # Find Q4 of prior year — should be at index (4 - latest_q) ... no wait,
    # records desc-sorted, so prior year's Q4 is at offset (4 - latest_q + 4)?
    # Actually: latest=QN(year Y), records[1..3]=QN-1..Q1 of Y, records[4]=Q4(Y-1)... no.
    # Records desc: [QN_Y, Q(N-1)_Y, ..., Q1_Y, Q4_Y-1, Q3_Y-1, ..., Q1_Y-1, Q4_Y-2, ...]
    # So Q4 of prior year is at index latest_q (offset from latest by latest_q quarters back).
    q4_prev_idx = latest_q  # e.g. latest=Q3 → records[3] should be Q4 of prior year
    if q4_prev_idx >= len(records):
        return None
    q4_prev = records[q4_prev_idx]
    if _fq_to_q(q4_prev.get("fq", "")) != 4:
        return None
    q4_prev_val = q4_prev.get(key)
    if q4_prev_val is None:
        return None

    return q4_prev_val + latest_val - same_q_prev_val


def _latest_stock(records: list[dict], key: str) -> float | None:
    """Latest non-null stock-item value (balance sheet)."""
    for r in records:
        v = r.get(key)
        if v is not None:
            return v
    return None


def compute_gp_to_assets(records: list[dict]) -> float | None:
    """Novy-Marx GP/A = gross_profit_TTM / total_assets (latest).

    Threshold guidance (Novy-Marx 2013):
      > 0.33 = strong; > 0.25 = OK; > 0.20 = acceptable for growth stocks
    """
    gp_ttm = ttm_from_cumulative(records, "gross_profit")
    assets = _latest_stock(records, "total_assets")
    if gp_ttm is None or not assets or assets <= 0:
        return None
    return round(gp_ttm / assets, 4)


def compute_accruals_ratio(records: list[dict]) -> float | None:
    """Sloan accruals = (NI_TTM - CFO_TTM) / avg_total_assets.

    Threshold guidance (Sloan 1996):
      < 0.05 = clean earnings; < 0.10 = OK; > 0.10 = quality concern
      Negative ratio (CFO > NI) is a positive signal — cash exceeds reported income.
    """
    ni_ttm = ttm_from_cumulative(records, "net_income")
    cfo_ttm = ttm_from_cumulative(records, "cfo")
    assets_now = _latest_stock(records, "total_assets")
    assets_4q = _stock_at_lag(records, "total_assets", 4)
    if ni_ttm is None or cfo_ttm is None or not assets_now:
        return None
    avg_assets = (assets_now + (assets_4q or assets_now)) / 2
    if avg_assets <= 0:
        return None
    return round((ni_ttm - cfo_ttm) / avg_assets, 4)


def _stock_at_lag(records: list[dict], key: str, lag_q: int) -> float | None:
    """Stock-item value lag_q quarters ago (records sorted desc)."""
    if len(records) <= lag_q:
        return None
    for r in records[lag_q:]:
        v = r.get(key)
        if v is not None:
            return v
    return None


def compute_piotroski_f_score(records: list[dict]) -> int | None:
    """Piotroski F-Score (0-9). Higher = more financial strength.

    Adapted to quarterly TTM data (original uses annual):
      Profitability (4 pts):
        1. ROA_TTM > 0
        2. CFO_TTM > 0
        3. dROA > 0 (TTM ROA > prior-year TTM ROA)
        4. CFO > NI (accruals quality)
      Leverage / liquidity / source (3 pts):
        5. dLeverage < 0 (total_liab / total_assets decreased YoY)
        6. dCurrent_ratio > 0  — SKIPPED (no current assets/liabilities granular)
           → reassigned to: dGP_margin > 0 (gross margin expansion)
        7. dShares_out <= 0 (no new dilution)
      Operating efficiency (2 pts):
        8. dGross_margin > 0  (covered by #6 reassigned)
           → reassigned to: dAsset_turnover > 0
        9. dAsset_turnover > 0  → SKIPPED to avoid double-count
           → final 9th: revenue_TTM growth > 0

    Returns None if < 5 quarters of data (can't compute YoY).
    """
    if len(records) < 5:
        return None

    ni_ttm = ttm_from_cumulative(records, "net_income")
    cfo_ttm = ttm_from_cumulative(records, "cfo")
    rev_ttm = ttm_from_cumulative(records, "revenue")
    gp_ttm = ttm_from_cumulative(records, "gross_profit")
    assets_now = _latest_stock(records, "total_assets")

    # Lag = 4 quarters ago — for "prior year TTM" comparison.
    # If insufficient prior history, prior TTMs become None and those F-Score
    # checks gracefully skip (no penalty, just lower max attainable).
    prior = records[4:] if len(records) >= 5 else []
    ni_prev = ttm_from_cumulative(prior, "net_income") if prior else None
    cfo_prev = ttm_from_cumulative(prior, "cfo") if prior else None
    rev_prev = ttm_from_cumulative(prior, "revenue") if prior else None
    gp_prev = ttm_from_cumulative(prior, "gross_profit") if prior else None
    assets_prev = _latest_stock(prior, "total_assets")
    liab_now = _latest_stock(records, "total_liab")
    liab_prev = _latest_stock(prior, "total_liab")
    shares_now = _latest_stock(records, "shares_out")
    shares_prev = _latest_stock(prior, "shares_out")

    score = 0

    # 1. ROA_TTM > 0
    if ni_ttm is not None and assets_now and ni_ttm > 0:
        score += 1
    # 2. CFO_TTM > 0
    if cfo_ttm is not None and cfo_ttm > 0:
        score += 1
    # 3. dROA > 0
    if (ni_ttm is not None and assets_now and ni_prev is not None and assets_prev
            and assets_now > 0 and assets_prev > 0):
        if (ni_ttm / assets_now) > (ni_prev / assets_prev):
            score += 1
    # 4. CFO > NI (accruals quality)
    if cfo_ttm is not None and ni_ttm is not None and cfo_ttm > ni_ttm:
        score += 1
    # 5. dLeverage < 0
    if liab_now and assets_now and liab_prev and assets_prev and assets_now > 0 and assets_prev > 0:
        if (liab_now / assets_now) < (liab_prev / assets_prev):
            score += 1
    # 6. dGross_margin > 0 (reassigned from current_ratio)
    if (gp_ttm is not None and rev_ttm and gp_prev is not None and rev_prev
            and rev_ttm > 0 and rev_prev > 0):
        if (gp_ttm / rev_ttm) > (gp_prev / rev_prev):
            score += 1
    # 7. dShares_out <= 0 (no dilution)
    if shares_now is not None and shares_prev is not None:
        if shares_now <= shares_prev * 1.005:  # 0.5% tolerance
            score += 1
    # 8. dAsset_turnover > 0
    if (rev_ttm and assets_now and rev_prev and assets_prev
            and assets_now > 0 and assets_prev > 0):
        if (rev_ttm / assets_now) > (rev_prev / assets_prev):
            score += 1
    # 9. revenue_TTM growth > 0
    if rev_ttm is not None and rev_prev is not None and rev_prev > 0:
        if rev_ttm > rev_prev:
            score += 1

    return score
