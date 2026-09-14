"""Export an allowlisted StockResearch snapshot for stock-growth-lab.

Runs inside StockResearch's existing credential boundary. Credential values are
used only for Supabase REST authentication and are never printed or serialized.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ALLOWED_STAGES = ["universe", "prices", "financials", "filings"]
STOCK_FIELDS = "ticker,market,name_kr,name_en,sector_wics,industry,is_active,created_at"
PRICE_FIELDS = "ticker,date,open,high,low,close,volume"
FINANCIAL_FIELDS = (
    "ticker,fq,revenue,op_income,net_income,op_margin,roe,roic,fcf,"
    "debt_ratio,interest_coverage,created_at"
)
FILING_FIELDS = (
    "id,ticker,source,filing_type,filed_at,url,headline,parsed_amount,"
    "parsed_customer,keywords,created_at"
)
PIPELINE_FIELDS = "stage,ended_at,status"

ROW_FIELDS = {
    "stocks": set(STOCK_FIELDS.split(",")),
    "prices_daily": set(PRICE_FIELDS.split(",")),
    "financials_q": set(FINANCIAL_FIELDS.split(",")),
    "filings": set(FILING_FIELDS.split(",")),
    "pipeline_runs": set(PIPELINE_FIELDS.split(",")),
}


def _require_kr_ticker(value: str) -> str:
    ticker = value.strip()
    if len(ticker) != 6 or not ticker.isdigit():
        raise SystemExit("ticker must be exactly six digits")
    return ticker


def _env_value(env_path: Path, name: str) -> str | None:
    direct = os.environ.get(name)
    if direct:
        return direct
    if not env_path.exists():
        return None
    for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, sep, value = line.partition("=")
        if not sep or key.strip() != name:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        return value
    return None


def _credentials() -> tuple[str, str]:
    collector_root = Path(__file__).resolve().parents[1]
    env_path = collector_root / ".env"
    base_url = _env_value(env_path, "SUPABASE_URL")
    service_key = _env_value(env_path, "SUPABASE_SERVICE_KEY")
    if not base_url or not service_key:
        raise SystemExit("StockResearch Supabase credentials are not configured")
    return base_url.rstrip("/"), service_key


def _get_rows(base_url: str, service_key: str, table: str, params: list[tuple[str, str]]) -> list[dict[str, Any]]:
    query = urlencode(params, safe="(),.*")
    request = Request(
        f"{base_url}/rest/v1/{table}?{query}",
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise SystemExit(f"Supabase request failed with HTTP {exc.code}") from None
    except URLError:
        raise SystemExit("Supabase request failed: network unavailable") from None
    if not isinstance(payload, list):
        raise SystemExit(f"Supabase returned unexpected payload for {table}")
    return payload


def build_snapshot(base_url: str, service_key: str, ticker: str) -> dict[str, Any]:
    stocks = _get_rows(base_url, service_key, "stocks", [
        ("select", STOCK_FIELDS), ("ticker", f"eq.{ticker}"),
        ("market", "in.(KOSPI,KOSDAQ)"), ("limit", "1"),
    ])
    if not stocks:
        raise SystemExit(f"No Korean stock row found for ticker {ticker}")

    prices = _get_rows(base_url, service_key, "prices_daily", [
        ("select", PRICE_FIELDS), ("ticker", f"eq.{ticker}"),
        ("order", "date.desc"), ("limit", "8"),
    ])
    financials = _get_rows(base_url, service_key, "financials_q", [
        ("select", FINANCIAL_FIELDS), ("ticker", f"eq.{ticker}"),
        ("order", "fq.desc"), ("limit", "12"),
    ])
    filings = _get_rows(base_url, service_key, "filings", [
        ("select", FILING_FIELDS), ("ticker", f"eq.{ticker}"),
        ("source", "eq.DART"), ("order", "filed_at.desc"), ("limit", "10"),
    ])
    pipeline_runs = _get_rows(base_url, service_key, "pipeline_runs", [
        ("select", PIPELINE_FIELDS),
        ("stage", "in.(universe,prices,financials,filings)"),
        ("order", "ended_at.desc.nullslast"), ("limit", "100"),
    ])
    return {
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "stocks": stocks,
        "prices_daily": prices,
        "financials_q": financials,
        "filings": filings,
        "pipeline_runs": pipeline_runs,
    }


def _assert_allowlisted(payload: dict[str, Any]) -> None:
    expected_top = {"retrieved_at", *ROW_FIELDS.keys()}
    if set(payload) != expected_top:
        raise SystemExit("refusing to write snapshot: unexpected top-level field")
    for table, allowed in ROW_FIELDS.items():
        for row in payload[table]:
            if set(row) - allowed:
                raise SystemExit(f"refusing to write snapshot: unexpected {table} field")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", default="005930")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    ticker = _require_kr_ticker(args.ticker)
    base_url, service_key = _credentials()
    payload = build_snapshot(base_url, service_key, ticker)
    _assert_allowlisted(payload)

    serialized = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    forbidden_markers = ["raw_text", "SUPABASE_SERVICE_KEY", "SUPABASE_URL", ".env", service_key]
    if any(marker and marker in serialized for marker in forbidden_markers):
        raise SystemExit("refusing to write snapshot: forbidden marker detected")

    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(serialized + "\n", encoding="utf-8")
    counts = {key: len(payload[key]) for key in ROW_FIELDS}
    print(json.dumps({"ticker": ticker, "output": str(output), "counts": counts}, ensure_ascii=False))


if __name__ == "__main__":
    main()
