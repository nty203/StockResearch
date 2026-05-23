"""Evaluate PPTR rule outcomes and update rule performance summaries."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from statistics import mean, median

from ..upsert import get_client, pipeline_run

logger = logging.getLogger(__name__)

HORIZONS_MONTHS = (3, 6, 12, 24)


def _parse_dt(value) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _safe_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _hit_rate(values: list[float], threshold: float) -> float | None:
    if not values:
        return None
    return round(sum(1 for v in values if v >= threshold) / len(values), 4)


def summarize_returns(returns: list[float]) -> dict:
    """Summarize multiplier returns where 1.0 means flat and 2.0 means +100%."""
    if not returns:
        return {
            "sample_size": 0,
            "avg_return": None,
            "median_return": None,
            "hit_rate_2x": None,
            "hit_rate_5x": None,
            "hit_rate_10x": None,
            "hit_rate_30x": None,
            "hit_rate_100x": None,
            "false_positive_rate": None,
        }
    return {
        "sample_size": len(returns),
        "avg_return": round(mean(returns), 4),
        "median_return": round(median(returns), 4),
        "hit_rate_2x": _hit_rate(returns, 2),
        "hit_rate_5x": _hit_rate(returns, 5),
        "hit_rate_10x": _hit_rate(returns, 10),
        "hit_rate_30x": _hit_rate(returns, 30),
        "hit_rate_100x": _hit_rate(returns, 100),
        "false_positive_rate": round(sum(1 for v in returns if v < 1.0) / len(returns), 4),
    }


def _fetch_close_near(client, ticker: str, target_date: str, forward_days: int = 14) -> float | None:
    end = (datetime.fromisoformat(target_date) + timedelta(days=forward_days)).date().isoformat()
    rows = (
        client.table("prices_daily")
        .select("date, close")
        .eq("ticker", ticker)
        .gte("date", target_date)
        .lte("date", end)
        .order("date", desc=False)
        .limit(1)
        .execute()
        .data
        or []
    )
    return _safe_float(rows[0].get("close")) if rows else None


def _returns_for_rule(client, rule_id: str, horizon_months: int, now: datetime) -> list[float]:
    cutoff = (now - timedelta(days=int(horizon_months * 30.5))).isoformat()
    matches = (
        client.table("pptr_rule_matches")
        .select("ticker, matched_at, as_of_close")
        .eq("rule_id", rule_id)
        .lte("matched_at", cutoff)
        .execute()
        .data
        or []
    )
    returns: list[float] = []
    for match in matches:
        ticker = match.get("ticker")
        matched_at = _parse_dt(match.get("matched_at"))
        if not ticker or matched_at is None:
            continue
        start_close = _safe_float(match.get("as_of_close")) or _fetch_close_near(
            client, ticker, matched_at.date().isoformat()
        )
        target_date = (matched_at + timedelta(days=int(horizon_months * 30.5))).date().isoformat()
        end_close = _fetch_close_near(client, ticker, target_date)
        if start_close and end_close and start_close > 0:
            returns.append(end_close / start_close)
    return returns


def run() -> int:
    client = get_client()
    now = datetime.now(timezone.utc)
    rows_written = 0
    with pipeline_run(client, "pptr_performance") as (rows_out, _):
        rules = client.table("pptr_rules").select("rule_id").execute().data or []
        for rule in rules:
            rule_id = rule.get("rule_id")
            if not rule_id:
                continue
            latest_summary = None
            for horizon in HORIZONS_MONTHS:
                summary = summarize_returns(_returns_for_rule(client, rule_id, horizon, now))
                if summary["sample_size"] == 0:
                    continue
                payload = {
                    "rule_id": rule_id,
                    "evaluated_at": now.isoformat(),
                    "horizon_months": horizon,
                    **summary,
                }
                client.table("pptr_rule_performance").insert(payload).execute()
                rows_written += 1
                if horizon == 12:
                    latest_summary = summary
            if latest_summary:
                client.table("pptr_rules").update({
                    "performance_summary": latest_summary,
                    "updated_at": now.isoformat(),
                }).eq("rule_id", rule_id).execute()
        rows_out[0] = rows_written
    logger.info("PPTR performance rows written: %d", rows_written)
    return rows_written


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    count = run()
    print(f"Done: {count} PPTR performance rows")
