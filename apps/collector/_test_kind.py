"""Test KIND scraper and full filings run."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv()
import logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')

from src.filings_watch import collect_kind_filings, run as filings_run
from src.upsert import get_client

client = get_client()

# Get KR tickers
res = client.table('stocks').select('ticker, market').eq('is_active', True).execute()
stocks = res.data or []
kr_ticker_set = {s['ticker'] for s in stocks if s['market'] in ('KOSPI', 'KOSDAQ')}
print(f'KR tickers in universe: {len(kr_ticker_set)}')

# Test KIND with 7-day lookback (catch recent filings)
print("\n[KIND 스크래핑 테스트 - 최근 7일]")
rows = collect_kind_filings(kr_ticker_set, lookback_days=7)
print(f'KIND rows collected: {len(rows)}')
if rows:
    for r in rows[:10]:
        kws = ', '.join(r.get('keywords', []))
        print(f"  [{r['ticker']}] {r['headline'][:60]}  kw={kws}")
else:
    print("  KIND 공시 없음 — API 응답 확인 필요")

# Now run full filings pipeline
print("\n[전체 공시 수집 실행]")
count = filings_run()
print(f"Total upserted: {count}")

# Check DB after
print("\n[DB 공시 현황]")
r = client.table('filings').select('ticker, headline, filed_at, source').order('filed_at', desc=True).limit(20).execute()
print(f"  Total recent filings: {len(r.data or [])}")
for row in (r.data or [])[:15]:
    print(f"  [{row['filed_at'][:10]}] {row.get('source','?'):<6} {row['ticker']:<8} {(row.get('headline') or '')[:55]}")
