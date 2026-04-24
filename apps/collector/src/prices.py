"""Price collector — daily OHLCV for KR (FinanceDataReader) and US (yfinance)."""
import logging
import time
from datetime import date, timedelta

import FinanceDataReader as fdr
import yfinance as yf

from .upsert import get_client, upsert_batch

logger = logging.getLogger(__name__)

TWO_YEARS_AGO = (date.today() - timedelta(days=730)).isoformat()
BATCH_SIZE = 20  # tickers per yfinance batch request


def collect_kr_prices(tickers: list[str]) -> list[dict]:
    rows = []
    for ticker in tickers:
        try:
            df = fdr.DataReader(ticker, TWO_YEARS_AGO)
            if df.empty:
                continue
            df = df.reset_index()
            for _, r in df.iterrows():
                rows.append({
                    "ticker": ticker,
                    "date": str(r["Date"])[:10],
                    "open": float(r["Open"]) if r["Open"] == r["Open"] else None,
                    "high": float(r["High"]) if r["High"] == r["High"] else None,
                    "low": float(r["Low"]) if r["Low"] == r["Low"] else None,
                    "close": float(r["Close"]),
                    "volume": int(r["Volume"]) if r["Volume"] == r["Volume"] else None,
                    "adj_close": float(r.get("Adj Close", r["Close"])),
                })
        except Exception as e:
            logger.warning("KR price error %s: %s", ticker, e)
    return rows


def collect_us_prices(tickers: list[str]) -> list[dict]:
    rows = []
    for i in range(0, len(tickers), BATCH_SIZE):
        batch = tickers[i : i + BATCH_SIZE]
        try:
            data = yf.download(
                batch, start=TWO_YEARS_AGO, auto_adjust=True, progress=False, threads=False
            )
            if data.empty:
                continue
            if isinstance(data.columns, type(data.columns)) and hasattr(data.columns, "levels"):
                for ticker in batch:
                    try:
                        t_df = data.xs(ticker, axis=1, level=1).dropna(subset=["Close"])
                    except KeyError:
                        continue
                    for dt, r in t_df.iterrows():
                        rows.append({
                            "ticker": ticker,
                            "date": str(dt)[:10],
                            "open": float(r.get("Open", None)) if r.get("Open") == r.get("Open") else None,
                            "high": float(r.get("High", None)) if r.get("High") == r.get("High") else None,
                            "low": float(r.get("Low", None)) if r.get("Low") == r.get("Low") else None,
                            "close": float(r["Close"]),
                            "volume": int(r.get("Volume", 0)) if r.get("Volume") == r.get("Volume") else None,
                            "adj_close": float(r["Close"]),
                        })
            time.sleep(0.5)
        except Exception as e:
            logger.warning("US price error batch %s: %s", batch[:3], e)
    return rows


def run(market_filter: str | None = None) -> int:
    client = get_client()
    res = client.table("stocks").select("ticker, market").eq("is_active", True).execute()
    stocks = res.data or []

    kr_tickers = [s["ticker"] for s in stocks if s["market"] in ("KOSPI", "KOSDAQ")]
    us_tickers = [s["ticker"] for s in stocks if s["market"] in ("NYSE", "NASDAQ")]

    if market_filter == "KR":
        rows = collect_kr_prices(kr_tickers)
    elif market_filter == "US":
        rows = collect_us_prices(us_tickers)
    else:
        rows = collect_kr_prices(kr_tickers) + collect_us_prices(us_tickers)

    count = upsert_batch(client, "prices_daily", rows, on_conflict="ticker,date")
    logger.info("Prices upserted %d rows", count)
    return count


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", help="Single ticker for smoke test")
    parser.add_argument("--market", choices=["KR", "US"])
    args = parser.parse_args()

    if args.ticker:
        from .upsert import get_client as _get
        c = _get()
        if args.ticker.isdigit():
            rows = collect_kr_prices([args.ticker])
        else:
            rows = collect_us_prices([args.ticker])
        upsert_batch(c, "prices_daily", rows, on_conflict="ticker,date")
        print(f"Upserted {len(rows)} rows for {args.ticker}")
    else:
        run(market_filter=args.market)
