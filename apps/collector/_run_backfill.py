"""Run price performance backfill for NULL matches."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv()
import logging
logging.basicConfig(level=logging.WARNING, format='%(levelname)s %(message)s')

from src.upsert import get_client

client = get_client()

# Check how many NULL price_performance entries exist
res = client.table("hundredx_category_matches").select("id", count="exact").is_("exited_at", "null").is_("price_current_multiplier", "null").execute()
null_count = res.count
print(f"NULL price_current_multiplier 수: {null_count:,}개")

res2 = client.table("hundredx_category_matches").select("id", count="exact").is_("exited_at", "null").not_.is_("price_current_multiplier", "null").execute()
filled_count = res2.count
print(f"채워진 price_current_multiplier 수: {filled_count:,}개")

if null_count == 0:
    print("backfill 필요 없음!")
else:
    print(f"\n가격 백필 실행 중 (limit=500)...")
    from src.hundredx.backfill_price_performance import run
    updated = run(client, dry_run=False, limit=500)
    print(f"업데이트: {updated}개")

    # Recheck
    res3 = client.table("hundredx_category_matches").select("id", count="exact").is_("exited_at", "null").is_("price_current_multiplier", "null").execute()
    print(f"남은 NULL: {res3.count:,}개")
