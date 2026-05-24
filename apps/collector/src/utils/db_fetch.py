"""Shared DB fetch utilities — reused by score.py and hundredx/scanner.py."""
from __future__ import annotations
import logging
from datetime import date, timedelta

logger = logging.getLogger(__name__)

# Minimum recency: financial data must be within this many months to be used
# as "current" signals for fingerprint matching.
# Library stocks have historical backfill (2019-2023); we don't want that
# treated as the stock's current financial state.
_MAX_STALE_MONTHS = 18


def _current_min_fq(ref_date: date | None = None) -> str:
    """Return the oldest fq string acceptable as 'current' data relative to ref_date.

    With _MAX_STALE_MONTHS=18 and ref_date=2026-05, returns '2024Q4' — anything
    older than that is considered historical, not current.
    """
    today = ref_date or date.today()
    # Subtract months safely
    total_months = today.year * 12 + today.month - _MAX_STALE_MONTHS
    year = total_months // 12
    month = total_months % 12
    if month == 0:
        month = 12
        year -= 1
    q = (month - 1) // 3 + 1
    return f"{year}Q{q}"


def _max_fq_for_as_of(as_of: date) -> str:
    """as_of 시점에 알 수 있는 가장 최근 분기 fq.

    분기 종료 후 ~45일 보고 지연 가정 (DART/SEC 분기보고서 일반 마감).
    예: as_of=2026-05-24 -> 2026-03-31 종료 분기는 5/15까지 마감 -> 2026Q1 사용 가능.
    """
    # 가장 보수적으로 45일 lag
    eff_date = as_of - timedelta(days=45)
    year = eff_date.year
    q = (eff_date.month - 1) // 3 + 1
    if q < 1:
        q = 4
        year -= 1
    return f"{year}Q{q}"


def bulk_fetch_financials(
    client,
    tickers: list[str],
    as_of_date: date | None = None,
) -> dict[str, dict]:
    """Batch-fetch financials and prices for up to 50 tickers (one query per table).

    Returns dict keyed by ticker. Each value contains:
      revenue_ttm, revenue_prev, revenue_2y_ago,
      op_margin_ttm, op_margin_prev,
      roic, fcf, debt_ratio,
      order_backlog, order_backlog_prev,
      price, price_52w_high, avg_daily_value

    IMPORTANT — data recency:
    Only quarterly records (fq like '2024Q3') within the last 18 months are used
    for TTM calculations. Annual records ('2022Y', '2025Y') from yfinance are
    intentionally excluded from the quarterly stream to prevent inflated TTM figures
    (annual revenue ≠ one quarter's worth). If a ticker's most-recent quarterly data
    is older than _MAX_STALE_MONTHS, it is treated as having no financial data — this
    prevents historical library-stock backfill from masquerading as current signals.
    """
    result: dict[str, dict] = {t: {"ticker": t} for t in tickers}

    ref_date = as_of_date or date.today()
    min_fq = _current_min_fq(ref_date)  # e.g. '2024Q4' when ref=2026-05
    max_fq = _max_fq_for_as_of(ref_date) if as_of_date else None  # 시점 여행 시에만 future 차단

    # Financials — quarterly only (fq matches 'YYYYQN' pattern, excludes 'YYYYY').
    # Fetch ~3 years of data per ticker, then filter in Python.
    fin_res = (
        client.table("financials_q")
        .select(
            "ticker, fq, revenue, op_income, op_margin, net_income, "
            "roe, roic, fcf, debt_ratio, order_backlog, "
            "gross_profit, cfo, total_assets, total_equity, total_liab, shares_out"
        )
        .in_("ticker", tickers)
        .like("fq", "%Q%")        # quarterly only — excludes '2022Y', '2025Y' etc.
        .order("fq", desc=True)
        .execute()
    )
    fins_by_ticker: dict[str, list] = {}
    for row in (fin_res.data or []):
        # Point-in-time guard: as_of_date 모드에선 미래 데이터 차단 (lookahead bias 방지)
        if max_fq is not None and row["fq"] > max_fq:
            continue
        fins_by_ticker.setdefault(row["ticker"], []).append(row)

    for ticker, fins in fins_by_ticker.items():
        # Sort desc by fq (already ordered, but ensure consistency)
        fins = sorted(fins, key=lambda r: r["fq"], reverse=True)

        # Recency guard: if the most-recent quarterly record is older than
        # _MAX_STALE_MONTHS, skip — this is historical backfill data, not
        # the stock's current financial state.
        if fins and fins[0]["fq"] < min_fq:
            logger.debug(
                "Skipping stale financials for %s: most recent fq=%s < %s",
                ticker, fins[0]["fq"], min_fq,
            )
            continue

        fins = fins[:12]  # 12 most recent quarters (3 years)
        if not fins:
            continue
        latest = fins[0]
        prev = fins[1] if len(fins) > 1 else {}
        data = result[ticker]
        # DART cumulative-quarterly aware TTM (Q4 = annual; Q1~Q3 = rolling-12 via prior Q4 + delta).
        from ..hundredx.quality_metrics import ttm_from_cumulative
        data["revenue_ttm"] = ttm_from_cumulative(fins, "revenue")
        data["revenue_prev"] = ttm_from_cumulative(fins[4:], "revenue") if len(fins) >= 5 else None
        data["revenue_2y_ago"] = ttm_from_cumulative(fins[8:], "revenue") if len(fins) >= 9 else None
        data["op_margin_ttm"] = latest.get("op_margin")
        data["op_margin_prev"] = prev.get("op_margin") if isinstance(prev, dict) else None
        data["roic"] = latest.get("roic")
        data["fcf"] = latest.get("fcf")
        data["debt_ratio"] = latest.get("debt_ratio")
        data["order_backlog"] = fins[0].get("order_backlog") if fins else None
        data["order_backlog_prev"] = fins[4].get("order_backlog") if len(fins) >= 5 else None
        # Store most-recent fq for downstream recency checks
        data["_latest_fq"] = fins[0]["fq"]

        # ── Quality / efficiency metrics (Piotroski / Sloan / Novy-Marx) ──────
        # Computed lazily from the same quarterly stream — no extra DB hit.
        from ..hundredx.quality_metrics import (
            compute_gp_to_assets,
            compute_accruals_ratio,
            compute_piotroski_f_score,
        )
        data["gp_to_assets"] = compute_gp_to_assets(fins)
        data["accruals_ratio"] = compute_accruals_ratio(fins)

        # ── ROIC 근사 (Greenblatt Magic Formula, Phelps 100-to-1) ───────────────
        # 정통 ROIC = NOPAT / Invested Capital. Cash 데이터 부재로 단순화:
        #   NOPAT_TTM ≈ op_income_TTM × 0.75 (한국 실효세율 ≈ 25%)
        #   Invested Capital ≈ total_assets (cash 미공제 보수적 추정)
        # Phelps 기준: ROIC > 9%; Greenblatt: > 15%.
        if latest.get("roic") is None:
            op_income_ttm = ttm_from_cumulative(fins, "op_income")
            assets = latest.get("total_assets")
            if op_income_ttm and assets and assets > 0:
                roic_approx = (op_income_ttm * 0.75) / assets * 100  # in %
                data["roic"] = round(roic_approx, 2)

        # ── Revenue QoQ acceleration (Asness et al. 2013) ─────────────────────
        # DART 분기 보고서는 누적 매출 보고 (Q1=3mo, Q2=6mo, Q3=9mo, Q4=12mo).
        # 단일 분기 매출로 변환 후 QoQ 비교 — 그렇지 않으면 Q1→Q2가 항상 +100%로 보임.
        # 같은 분기끼리 YoY 비교가 가장 안전 (계절성 + cumulative 모두 해결).
        if len(fins) >= 5:
            q0 = fins[0].get("revenue")        # 현재 분기 (누적)
            q_yoy = fins[4].get("revenue")     # 전년 동분기 (누적, 같은 분기 위치)
            q_1_yoy = fins[5].get("revenue") if len(fins) >= 6 else None  # 2년 전 동분기
            if q0 and q_yoy and q_yoy > 0:
                rev_yoy_now = (q0 - q_yoy) / q_yoy * 100
                data["revenue_yoy_now"] = round(rev_yoy_now, 2)
                if q_1_yoy and q_1_yoy > 0:
                    rev_yoy_prev = (q_yoy - q_1_yoy) / q_1_yoy * 100
                    # acceleration = 올해 YoY가 작년 YoY보다 가속됐는가 (pp 단위)
                    data["revenue_qoq_acceleration"] = round(rev_yoy_now - rev_yoy_prev, 2)
        data["f_score"] = compute_piotroski_f_score(fins)

    # Prices — fetch last ~300 calendar days (covers 252 trading days) up to ref_date.
    # 50 tickers × 300 days × ~50 bytes ≈ 750KB per batch.
    price_cutoff = (ref_date - timedelta(days=300)).isoformat()
    price_query = (
        client.table("prices_daily")
        .select("ticker, date, close, volume")
        .in_("ticker", tickers)
        .gte("date", price_cutoff)
    )
    if as_of_date is not None:
        price_query = price_query.lte("date", ref_date.isoformat())
    price_res = (
        price_query
        .order("date", desc=True)
        .execute()
    )
    prices_by_ticker: dict[str, list] = {}
    for row in (price_res.data or []):
        t = row["ticker"]
        if len(prices_by_ticker.get(t, [])) < 252:
            prices_by_ticker.setdefault(t, []).append(row)

    for ticker, prices in prices_by_ticker.items():
        if not prices:
            continue
        data = result[ticker]
        data["price"] = prices[0]["close"]
        data["price_52w_high"] = max(p["close"] for p in prices)
        recent = prices[:20]
        avg_vol = sum(p.get("volume") or 0 for p in recent) / len(recent)
        avg_price_val = sum(p["close"] for p in recent) / len(recent)
        data["avg_daily_value"] = avg_vol * avg_price_val if avg_vol > 0 else None
        baseline = prices[20:80]
        baseline_avg_vol = (
            sum(p.get("volume") or 0 for p in baseline) / len(baseline)
            if baseline
            else avg_vol
        )
        if baseline_avg_vol > 0:
            data["max_volume_spike_ratio"] = max((p.get("volume") or 0) / baseline_avg_vol for p in recent)

    return result
