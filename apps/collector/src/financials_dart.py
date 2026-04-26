"""DART quarterly financials collector via OpenDartReader."""
import logging
import os
import time

import OpenDartReader as DartReader

from .upsert import get_client, upsert_batch, pipeline_run

logger = logging.getLogger(__name__)

DART_API_KEY = os.environ.get("DART_API_KEY", "")

# Map DART reprt_code to quarters: 11013=Q1, 11012=Q2, 11014=Q3, 11011=Q4/Annual
REPRT_CODES = {
    "11013": "Q1",
    "11012": "Q2",
    "11014": "Q3",
    "11011": "Q4",
}


def _safe_float(v) -> float | None:
    if v is None:
        return None
    try:
        return float(str(v).replace(",", ""))
    except (ValueError, TypeError):
        return None


def collect_dart_financials(tickers: list[str], years: list[int]) -> list[dict]:
    if not DART_API_KEY:
        logger.error("DART_API_KEY not set")
        return []

    dart = DartReader(DART_API_KEY)
    rows = []

    for ticker in tickers:
        for year in years:
            for reprt_code, quarter_suffix in REPRT_CODES.items():
                fq = f"{year}{quarter_suffix}"
                try:
                    df = dart.finstate(ticker, year, reprt_code=reprt_code)
                    if df is None or df.empty:
                        continue
                    # Parse key metrics from IFRS statements
                    row = _parse_dart_df(df, ticker, fq)
                    if row:
                        rows.append(row)
                    time.sleep(0.1)  # DART rate limit: stay well under 20k/day
                except Exception as e:
                    logger.warning("DART error %s %s: %s", ticker, fq, e)
    return rows


def _parse_dart_df(df, ticker: str, fq: str) -> dict | None:
    """Extract key financial metrics from DART IFRS dataframe."""
    def get_amount(account_nm: str) -> float | None:
        mask = df["account_nm"].str.contains(account_nm, na=False)
        rows = df[mask]
        if rows.empty:
            return None
        val = rows.iloc[0].get("thstrm_amount", rows.iloc[0].get("당기"))
        return _safe_float(val)

    revenue = get_amount("매출액") or get_amount("수익(매출액)")
    op_income = get_amount("영업이익")
    net_income = get_amount("당기순이익")
    if revenue is None and op_income is None:
        return None

    op_margin = (op_income / revenue * 100) if (revenue and op_income) else None

    return {
        "ticker": ticker,
        "fq": fq,
        "revenue": revenue,
        "op_income": op_income,
        "net_income": net_income,
        "op_margin": op_margin,
        "roe": None,
        "roic": None,
        "fcf": None,
        "debt_ratio": None,
        "interest_coverage": None,
    }


def run(years: list[int] | None = None) -> int:
    from datetime import date
    if years is None:
        y = date.today().year
        years = [y - 2, y - 1, y]

    client = get_client()
    res = client.table("stocks").select("ticker").in_("market", ["KOSPI", "KOSDAQ"]).eq("is_active", True).execute()
    tickers = [r["ticker"] for r in (res.data or [])]

    with pipeline_run(client, "financials") as (rows_out, _):
        rows = collect_dart_financials(tickers, years)
        count = upsert_batch(client, "financials_q", rows, on_conflict="ticker,fq")
        rows_out[0] = count
    logger.info("DART financials upserted %d rows", count)
    return count


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
