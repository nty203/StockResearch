"""SEC EDGAR quarterly financials collector via edgartools."""
import logging
import time
from datetime import date

import edgar
from edgar import Company

from .upsert import get_client, upsert_batch

logger = logging.getLogger(__name__)

# EDGAR requires identity for rate limit compliance
EDGAR_IDENTITY = "StockResearch contact@example.com"


def _safe_float(v) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _fiscal_quarter(period_end: str) -> str:
    """Convert YYYY-MM-DD period end to fq format YYYYQ[1-4]."""
    month = int(period_end[5:7])
    year = int(period_end[:4])
    q = (month - 1) // 3 + 1
    return f"{year}Q{q}"


def collect_sec_financials(tickers: list[str]) -> list[dict]:
    edgar.set_identity(EDGAR_IDENTITY)
    rows = []

    for ticker in tickers:
        try:
            company = Company(ticker)
            filings = company.get_filings(form="10-Q").latest(8)
            for filing in filings:
                try:
                    financials = filing.financials
                    if financials is None:
                        continue
                    income = financials.income_statement
                    if income is None:
                        continue

                    period = str(filing.period_of_report or "")[:10]
                    if not period:
                        continue
                    fq = _fiscal_quarter(period)

                    revenue = _safe_float(getattr(income, "Revenues", None) or getattr(income, "RevenueFromContractWithCustomer", None))
                    op_income = _safe_float(getattr(income, "OperatingIncomeLoss", None))
                    net_income = _safe_float(getattr(income, "NetIncomeLoss", None))
                    op_margin = (op_income / revenue * 100) if (revenue and op_income) else None

                    rows.append({
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
                    })
                    time.sleep(0.1)  # SEC rate limit: 10 req/sec
                except Exception as e:
                    logger.warning("SEC filing parse error %s: %s", ticker, e)
            time.sleep(0.2)
        except Exception as e:
            logger.warning("SEC company error %s: %s", ticker, e)
    return rows


def run() -> int:
    client = get_client()
    res = client.table("stocks").select("ticker").in_("market", ["NYSE", "NASDAQ"]).eq("is_active", True).execute()
    tickers = [r["ticker"] for r in (res.data or [])]

    rows = collect_sec_financials(tickers)
    count = upsert_batch(client, "financials_q", rows, on_conflict="ticker,fq")
    logger.info("SEC financials upserted %d rows", count)
    return count


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
