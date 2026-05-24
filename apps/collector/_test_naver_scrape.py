"""Test NAVER filings scraper."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv()
import logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')

from src.filings_watch import collect_naver_filings
from supabase import create_client

client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

# Get KR tickers (top 100 active by market cap proxy = all active KOSPI/KOSDAQ)
res = client.table("stocks").select("ticker, market").eq("is_active", True).in_("market", ["KOSPI", "KOSDAQ"]).execute()
kr_ticker_set = {r["ticker"] for r in (res.data or [])}
print(f"KR tickers: {len(kr_ticker_set)}")

# Test with small subset first (30 tickers) to verify API works
import random
sample_tickers = set(random.sample(list(kr_ticker_set), min(30, len(kr_ticker_set))))

print("\n[NAVER 공시 스크래핑 테스트 - 30개 종목]")
rows = collect_naver_filings(sample_tickers, lookback_days=7)
print(f"\n수집된 공시: {len(rows)}개")
for r in rows[:10]:
    kws = ', '.join(r.get('keywords', []))
    print(f"  [{r['ticker']}] {r['headline'][:60]}  kw={kws}")

if rows:
    print("\n[실제 filings_watch.run() 실행]")
    from src.filings_watch import run
    count = run()
    print(f"총 upserted: {count}개")

    # DB status
    total = client.table("filings").select("*", count="exact").execute()
    print(f"DB filings 총: {total.count}개")
