"""
Library stock historical financials via yfinance.

Fetches FY annual income statement data (revenue, op_income, op_margin)
and stores in financials_q with fq='2022Y', '2023Y', etc.

Coverage: FY2022-2025 (4 years of annual data per stock)
Best for: library stocks with rise_start_date >= 2023-01

Usage:
  python _backfill_yfinance.py               # all library stocks
  python _backfill_yfinance.py --ticker 042700
  python _backfill_yfinance.py --dry-run
"""
import os, sys, io, time, argparse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, 'src')
from dotenv import load_dotenv; load_dotenv()

import yfinance as yf
from supabase import create_client

c = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_KEY'])


def get_yf_suffix(market: str) -> str:
    """KOSPI → .KS, KOSDAQ → .KQ"""
    if market == 'KOSDAQ':
        return '.KQ'
    return '.KS'  # KOSPI and unknown default to .KS


def fetch_annual_financials(ticker: str, suffix: str) -> list[dict]:
    """Fetch annual income statement rows from yfinance. Returns list of dicts."""
    yf_ticker = f"{ticker}{suffix}"
    rows = []
    try:
        tk = yf.Ticker(yf_ticker)
        inc = tk.income_stmt  # annual
        if inc is None or inc.empty:
            print(f"  [{ticker}] yfinance: no income_stmt for {yf_ticker}")
            return []

        for col in inc.columns:
            year = col.year  # pandas Timestamp
            fq = f"{year}Y"
            revenue = None
            op_income = None
            net_income = None

            if 'Total Revenue' in inc.index:
                v = inc.loc['Total Revenue', col]
                if v is not None and str(v) not in ('nan', 'NaN'):
                    try:
                        revenue = float(v)
                    except (ValueError, TypeError):
                        pass

            if 'Operating Income' in inc.index:
                v = inc.loc['Operating Income', col]
                if v is not None and str(v) not in ('nan', 'NaN'):
                    try:
                        op_income = float(v)
                    except (ValueError, TypeError):
                        pass

            if 'Net Income' in inc.index:
                v = inc.loc['Net Income', col]
                if v is not None and str(v) not in ('nan', 'NaN'):
                    try:
                        net_income = float(v)
                    except (ValueError, TypeError):
                        pass

            # Compute op_margin
            op_margin = None
            if revenue and revenue > 0 and op_income is not None:
                try:
                    op_margin = round(op_income / revenue * 100, 4)
                except (ZeroDivisionError, TypeError):
                    pass

            if revenue is None and op_income is None:
                continue  # skip empty year

            rows.append({
                'ticker': ticker,
                'fq': fq,
                'revenue': revenue,
                'op_income': op_income,
                'net_income': net_income,
                'op_margin': op_margin,
            })

    except Exception as e:
        print(f"  [{ticker}] yfinance ERROR: {e}")

    return rows


def upsert_financials(rows: list[dict], dry_run: bool = False) -> int:
    """Upsert rows into financials_q. Returns count of upserted rows."""
    if not rows:
        return 0
    if dry_run:
        for r in rows:
            rev_b = f"{r['revenue']/1e8:.1f}억" if r.get('revenue') else 'N/A'
            opm = f"{r['op_margin']:.1f}%" if r.get('op_margin') is not None else 'N/A'
            print(f"    [DRY] {r['ticker']} {r['fq']}: revenue={rev_b}, OPM={opm}")
        return len(rows)

    try:
        c.table('financials_q').upsert(
            rows,
            on_conflict='ticker,fq'
        ).execute()
        return len(rows)
    except Exception as e:
        # Try inserting one by one if bulk upsert fails
        inserted = 0
        for row in rows:
            try:
                c.table('financials_q').upsert(
                    row,
                    on_conflict='ticker,fq'
                ).execute()
                inserted += 1
            except Exception as e2:
                print(f"    Insert failed {row['ticker']} {row['fq']}: {e2}")
        return inserted


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ticker', help='Process only this ticker')
    parser.add_argument('--dry-run', action='store_true', help='Print without inserting')
    args = parser.parse_args()

    # Get library stocks
    lib_r = c.table('hundredx_library_stocks').select('ticker,rise_start_date').execute()
    lib_rows = lib_r.data or []

    # Unique tickers
    if args.ticker:
        tickers = [args.ticker]
    else:
        tickers = sorted(set(row['ticker'] for row in lib_rows))

    print(f"Processing {len(tickers)} unique tickers...")

    # Get market info
    stocks_r = c.table('stocks').select('ticker,market').in_('ticker', tickers).execute()
    market_map = {row['ticker']: row['market'] for row in (stocks_r.data or [])}

    total_upserted = 0
    for ticker in tickers:
        market = market_map.get(ticker, 'KOSPI')
        suffix = get_yf_suffix(market)

        print(f"\n{ticker} ({market}{suffix})")
        rows = fetch_annual_financials(ticker, suffix)
        if not rows:
            # Try the other suffix if first fails
            alt_suffix = '.KQ' if suffix == '.KS' else '.KS'
            print(f"  Retrying with {alt_suffix}...")
            rows = fetch_annual_financials(ticker, alt_suffix)

        if rows:
            n = upsert_financials(rows, dry_run=args.dry_run)
            total_upserted += n
            for r in rows:
                rev_b = f"{r['revenue']/1e8:.1f}억" if r.get('revenue') else 'N/A'
                opm = f"{r['op_margin']:.1f}%" if r.get('op_margin') is not None else 'N/A'
                print(f"  {r['fq']}: revenue={rev_b}, OPM={opm}")
        else:
            print(f"  No data found")

        time.sleep(0.5)  # rate limit

    print(f"\n=== 완료: {total_upserted}개 레코드 upserted ===")


if __name__ == '__main__':
    main()
