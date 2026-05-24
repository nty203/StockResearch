"""DB 전체 현황 빠른 점검."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv()
from supabase import create_client

client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

tables = [
    "stocks", "prices_daily", "filings", "news_articles",
    "hundredx_category_matches", "hundredx_library_stocks",
    "pptr_training_samples",
]

print("\n[DB 테이블 현황]")
for t in tables:
    try:
        r = client.table(t).select("*", count="exact").limit(1).execute()
        count = r.count
        sample = r.data[0] if r.data else {}
        # Get most recent date field
        date_val = (
            sample.get("filed_at") or sample.get("date") or
            sample.get("detected_at") or sample.get("created_at") or "?"
        )
        print(f"  {t:<40} {count:>8,}개  (sample date: {str(date_val)[:10]})")
    except Exception as e:
        print(f"  {t:<40} ERROR: {e}")

# Filings 최근 10개
print("\n[최근 공시 10개]")
try:
    r = client.table("filings").select("ticker, headline, filed_at").order("filed_at", desc=True).limit(10).execute()
    for row in (r.data or []):
        print(f"  [{row['filed_at'][:10]}] {row['ticker']:<8} {(row.get('headline') or '')[:60]}")
    if not r.data:
        print("  (없음)")
except Exception as e:
    print(f"  ERROR: {e}")

# Category matches 현황
print("\n[Category Matches 현황]")
try:
    r = client.table("hundredx_category_matches").select("category", count="exact").is_("exited_at", "null").execute()
    # Group by category manually
    all_matches = client.table("hundredx_category_matches").select("ticker, category, confidence, detected_at").is_("exited_at", "null").order("confidence", desc=True).limit(200).execute()
    from collections import Counter
    cat_counts = Counter(m["category"] for m in (all_matches.data or []))
    print(f"  총 활성 매칭: {r.count}개")
    for cat, cnt in sorted(cat_counts.items(), key=lambda x: -x[1]):
        print(f"    {cat:<25} {cnt:>5}개")
except Exception as e:
    print(f"  ERROR: {e}")

# Stocks 현황
print("\n[Stocks 현황]")
try:
    kr = client.table("stocks").select("market", count="exact").in_("market", ["KOSPI", "KOSDAQ"]).eq("is_active", True).execute()
    us = client.table("stocks").select("market", count="exact").in_("market", ["NYSE", "NASDAQ"]).eq("is_active", True).execute()
    print(f"  활성 KR: {kr.count:,}개")
    print(f"  활성 US: {us.count:,}개")
except Exception as e:
    print(f"  ERROR: {e}")

# Most recent price data
print("\n[최근 가격 데이터]")
try:
    r = client.table("prices_daily").select("ticker, date, close").order("date", desc=True).limit(5).execute()
    for row in (r.data or []):
        print(f"  [{row['date']}] {row['ticker']:<8} {row['close']}")
except Exception as e:
    print(f"  ERROR: {e}")
