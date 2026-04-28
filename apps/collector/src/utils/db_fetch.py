"""Shared DB fetch utilities — reused by score.py and hundredx/scanner.py."""
from __future__ import annotations
import logging
from datetime import date, timedelta

logger = logging.getLogger(__name__)


def bulk_fetch_financials(client, tickers: list[str]) -> dict[str, dict]:
    """Batch-fetch financials and prices for up to 50 tickers (one query per table).

    Returns dict keyed by ticker. Each value contains:
      revenue_ttm, revenue_prev, revenue_2y_ago,
      op_margin_ttm, op_margin_prev,
      roic, fcf, debt_ratio,
      order_backlog, order_backlog_prev,
      price, price_52w_high, avg_daily_value
    """
    result: dict[str, dict] = {t: {"ticker": t} for t in tickers}

    # Financials — fetch 12 most recent quarters (3 years) per ticker.
    # Supabase doesn't support LIMIT per group, so fetch and slice in Python.
    fin_res = (
        client.table("financials_q")
        .select("ticker, fq, revenue, op_income, op_margin, roe, roic, fcf, debt_ratio, order_backlog")
        .in_("ticker", tickers)
        .order("fq", desc=True)
        .execute()
    )
    fins_by_ticker: dict[str, list] = {}
    for row in (fin_res.data or []):
        fins_by_ticker.setdefault(row["ticker"], []).append(row)

    for ticker, fins in fins_by_ticker.items():
        fins = fins[:12]  # 12 most recent quarters (3 years)
        if not fins:
            continue
        latest = fins[0]
        prev = fins[1] if len(fins) > 1 else {}
        data = result[ticker]
        data["revenue_ttm"] = sum(f.get("revenue", 0) or 0 for f in fins[:4]) or None
        data["revenue_prev"] = sum(f.get("revenue", 0) or 0 for f in fins[4:8]) or None
        data["revenue_2y_ago"] = sum(f.get("revenue", 0) or 0 for f in fins[8:12]) or None
        data["op_margin_ttm"] = latest.get("op_margin")
        data["op_margin_prev"] = prev.get("op_margin") if isinstance(prev, dict) else None
        data["roic"] = latest.get("roic")
        data["fcf"] = latest.get("fcf")
        data["debt_ratio"] = latest.get("debt_ratio")
        data["order_backlog"] = fins[0].get("order_backlog") if fins else None
        data["order_backlog_prev"] = fins[4].get("order_backlog") if len(fins) >= 5 else None

    # Prices — fetch last ~300 calendar days (covers 252 trading days).
    # 50 tickers × 300 days × ~50 bytes ≈ 750KB per batch.
    price_cutoff = (date.today() - timedelta(days=300)).isoformat()
    price_res = (
        client.table("prices_daily")
        .select("ticker, date, close, volume")
        .in_("ticker", tickers)
        .gte("date", price_cutoff)
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

    return result
