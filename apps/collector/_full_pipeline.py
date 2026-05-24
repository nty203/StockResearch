"""전체 파이프라인 실행: NAVER 공시 수집 → 스캐너 → 결과 확인."""
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

from supabase import create_client
client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

print("=" * 70)
print("전체 파이프라인 실행")
print("=" * 70)

# Step 1: DB 현황
print("\n[1단계] 현재 DB 상태")
r = client.table("filings").select("*", count="exact").execute()
print(f"  공시 총: {r.count}개")
r2 = client.table("hundredx_category_matches").select("*", count="exact").is_("exited_at", "null").execute()
print(f"  활성 매칭: {r2.count}개")

# Step 2: NAVER 공시 수집
print("\n[2단계] NAVER Finance 공시 수집 (최근 7일, 최대 300종목)...")
from src.filings_watch import run as filings_run
count = filings_run()
print(f"  공시 upserted: {count}개")

r = client.table("filings").select("*", count="exact").execute()
print(f"  공시 총: {r.count}개")

# Step 3: 스캐너 실행
print("\n[3단계] 100배 스캐너 실행 중...")
from src.hundredx.scanner import run as scanner_run
new_matches = scanner_run(0.70)
print(f"  새 매칭 upserted: {new_matches}개")

# Step 4: 결과 확인
print("\n[4단계] 결과 분석")
r3 = client.table("hundredx_category_matches").select("*", count="exact").is_("exited_at", "null").execute()
print(f"  활성 매칭 총: {r3.count}개")

# 최근 공시 기반 탐지 확인
print("\n[최근 탐지된 공시 기반 매칭]")
recent = (
    client.table("hundredx_category_matches")
    .select("ticker, category, confidence, detected_at")
    .is_("exited_at", "null")
    .order("detected_at", desc=True)
    .limit(30)
    .execute()
)
from collections import Counter
cat_counter = Counter()
for m in (recent.data or []):
    cat_counter[m["category"]] += 1
    dt = str(m["detected_at"])[:16]
    print(f"  [{dt}] {m['ticker']:<8} {m['category']:<25} conf={m['confidence']:.3f}")

print(f"\n[카테고리 분포 (최근 30개)]")
for cat, cnt in sorted(cat_counter.items(), key=lambda x: -x[1]):
    print(f"  {cat:<25} {cnt}개")

# 최근 실제 공시 확인
print("\n[DB에 수집된 최근 실제 공시]")
filings_res = (
    client.table("filings")
    .select("ticker, headline, filed_at, source, keywords")
    .not_.eq("source", "SEED")
    .order("filed_at", desc=True)
    .limit(20)
    .execute()
)
for f in (filings_res.data or []):
    kws = str(f.get("keywords") or [])[:30]
    print(f"  [{f['filed_at'][:10]}] {f.get('source','?'):<5} {f['ticker']:<8} {(f.get('headline') or '')[:55]}")

print("\n완료!")
