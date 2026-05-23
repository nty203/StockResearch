"""Price performance helpers for current hundredx matches.

The daily prices table is intentionally pruned, so current signal cards cannot
rely on it for multi-year moves. These helpers fetch a compact history only for
matched tickers and compute:

- current multiplier: latest close / baseline close
- current return pct: (current multiplier - 1) * 100
- peak multiplier: highest close after baseline / baseline close
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import logging
from typing import Iterable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PricePerformance:
    baseline_date: str
    baseline_close: float
    latest_date: str
    latest_close: float
    peak_date: str
    peak_close: float
    current_multiplier: float
    current_return_pct: float
    peak_multiplier: float
    peak_return_pct: float


PricePoint = tuple[str, float]


def _round_price(value: float) -> float:
    return round(float(value), 4)


def _round_multiplier(value: float) -> float:
    return round(float(value), 3)


def _round_pct(value: float) -> float:
    return round(float(value), 1)


def _clean_points(prices: Iterable[PricePoint]) -> list[PricePoint]:
    points: list[PricePoint] = []
    for raw_date, raw_close in prices:
        try:
            close = float(raw_close)
        except (TypeError, ValueError):
            continue
        if close <= 0:
            continue
        points.append((str(raw_date)[:10], close))
    return sorted(points, key=lambda p: p[0])


def _build_performance(points: list[PricePoint], baseline: PricePoint) -> PricePerformance | None:
    if not points:
        return None

    latest = points[-1]
    if baseline[1] <= 0:
        return None

    after_baseline = [p for p in points if p[0] >= baseline[0]]
    if not after_baseline:
        return None
    peak = max(after_baseline, key=lambda p: p[1])

    current_multiplier = latest[1] / baseline[1]
    peak_multiplier = peak[1] / baseline[1]

    return PricePerformance(
        baseline_date=baseline[0],
        baseline_close=_round_price(baseline[1]),
        latest_date=latest[0],
        latest_close=_round_price(latest[1]),
        peak_date=peak[0],
        peak_close=_round_price(peak[1]),
        current_multiplier=_round_multiplier(current_multiplier),
        current_return_pct=_round_pct((current_multiplier - 1.0) * 100.0),
        peak_multiplier=_round_multiplier(peak_multiplier),
        peak_return_pct=_round_pct((peak_multiplier - 1.0) * 100.0),
    )


def compute_window_performance(prices: Iterable[PricePoint]) -> PricePerformance | None:
    """Return performance from the lowest close in the supplied window."""
    points = _clean_points(prices)
    if len(points) < 2:
        return None
    baseline = min(points, key=lambda p: p[1])
    return _build_performance(points, baseline)


def compute_since_date_performance(
    prices: Iterable[PricePoint],
    target_date: str,
    forward_days: int = 14,
) -> PricePerformance | None:
    """Return performance from the first trading close near ``target_date``."""
    points = _clean_points(prices)
    if len(points) < 2:
        return None

    target = datetime.fromisoformat(target_date[:10]).date()
    end = target + timedelta(days=forward_days)
    baseline = next(
        (
            p for p in points
            if target <= datetime.fromisoformat(p[0]).date() <= end
        ),
        None,
    )
    if baseline is None:
        baseline = points[0]
    return _build_performance(points, baseline)


def _is_kr_ticker(ticker: str, market: str | None) -> bool:
    return ticker.isdigit() or market in {"KOSPI", "KOSDAQ"}


def _fetch_kr_prices(ticker: str, start: str) -> list[PricePoint]:
    import FinanceDataReader as fdr

    df = fdr.DataReader(ticker, start)
    if df.empty:
        return []
    df = df.reset_index().sort_values("Date")
    return [
        (str(row["Date"])[:10], float(row["Close"]))
        for _, row in df.iterrows()
        if row.get("Close") == row.get("Close")
    ]


def _fetch_us_prices(ticker: str, start: str) -> list[PricePoint]:
    import yfinance as yf

    df = yf.download(
        ticker,
        start=start,
        auto_adjust=True,
        progress=False,
        threads=False,
    )
    if df.empty:
        return []

    close = df["Close"]
    if hasattr(close, "columns"):
        close = close.iloc[:, 0]

    return [
        (str(idx)[:10], float(value))
        for idx, value in close.items()
        if value == value
    ]


def fetch_price_points(ticker: str, market: str | None, start: str) -> list[PricePoint]:
    if _is_kr_ticker(ticker, market):
        return _fetch_kr_prices(ticker, start)
    return _fetch_us_prices(ticker, start)


def fetch_window_performance(
    ticker: str,
    market: str | None = None,
    years: int = 3,
) -> PricePerformance | None:
    """Fetch recent history and compute current move from the window low."""
    start = (date.today() - timedelta(days=int(years * 365.25))).isoformat()
    try:
        return compute_window_performance(fetch_price_points(ticker, market, start))
    except Exception as exc:
        logger.warning("price performance fetch failed for %s: %s", ticker, exc)
        return None


def fetch_since_date_performance(
    ticker: str,
    market: str | None,
    target_date: str,
) -> PricePerformance | None:
    """Fetch history from a known rise start date and compute current/peak move."""
    try:
        return compute_since_date_performance(
            fetch_price_points(ticker, market, target_date),
            target_date,
        )
    except Exception as exc:
        logger.warning("price performance fetch failed for %s since %s: %s", ticker, target_date, exc)
        return None
