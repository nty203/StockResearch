"""탐지 결과 이슈 진단."""
import os, sys
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv()
from supabase import create_client

client = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_KEY'])

# 이슈1: 083450 카테고리 중복 — dedup 작동 안 하는 건지?
print("=== 이슈1: 083450 카테고리 중복 ===")
r = client.table('hundredx_category_matches').select('ticker,category,confidence,detected_at,exited_at').eq('ticker','083450').execute()
for m in (r.data or []):
    status = 'EXIT' if m.get('exited_at') else 'ACTIVE'
    print(f"  [{status}] {m['category']:<25} conf={m['confidence']:.3f}  detected={str(m['detected_at'])[:16]}")

# 이슈2: 미분류/단기_테마_급등 출처
print("\n=== 이슈2: 미분류 + 단기_테마_급등 샘플 ===")
for cat in ['미분류', '단기_테마_급등']:
    r2 = client.table('hundredx_category_matches').select('ticker,category,confidence,evidence').is_('exited_at','null').eq('category', cat).limit(3).execute()
    for m in (r2.data or []):
        evid = m.get('evidence') or []
        sources = list({e.get('source_type','?') for e in evid if isinstance(e, dict)})
        kws = [e.get('keyword') or e.get('text','') for e in evid[:3] if isinstance(e, dict)]
        print(f"  {m['ticker']:<8} {cat:<20} conf={m['confidence']:.3f}  sources={sources}  kws={kws[:3]}")

# 이슈3: 005930 미탐지 원인
print("\n=== 이슈3: 005930 (삼성전자) 미탐지 원인 ===")
r3 = client.table('stocks').select('ticker,market,is_active,sector_tag').eq('ticker','005930').execute()
for s in (r3.data or []):
    print(f"  DB: is_active={s['is_active']}  market={s['market']}  sector={s['sector_tag']}")
r3b = client.table('hundredx_category_matches').select('ticker,category,confidence,exited_at').eq('ticker','005930').execute()
if r3b.data:
    for m in r3b.data:
        print(f"  match: {m['category']} conf={m['confidence']} exited={m.get('exited_at')}")
else:
    print("  category_matches: 없음")

# 이슈4: 440110 (파두) 미탐지
print("\n=== 이슈4: 440110 (파두) 미탐지 원인 ===")
r4 = client.table('stocks').select('ticker,market,is_active,sector_tag').eq('ticker','440110').execute()
for s in (r4.data or []):
    print(f"  DB: is_active={s['is_active']}  market={s['market']}  sector={s['sector_tag']}")
r4b = client.table('filings').select('ticker,headline,keywords').eq('ticker','440110').execute()
for f in (r4b.data or []):
    print(f"  filing: {f.get('headline')}  kws={f.get('keywords')}")

# 이슈5: 298040 이미 50배 종목 — 탐지 시점이 너무 늦은 건지?
print("\n=== 이슈5: 이미 고배수 종목 탐지 시점 분석 ===")
r5 = client.table('hundredx_category_matches').select(
    'ticker,category,confidence,first_detected_at,price_baseline_date,price_current_multiplier,price_peak_multiplier'
).is_('exited_at','null').gte('price_current_multiplier', 10).execute()
for m in sorted(r5.data or [], key=lambda x: -(x.get('price_current_multiplier') or 0)):
    baseline = str(m.get('price_baseline_date') or '')[:7]
    detected = str(m.get('first_detected_at') or '')[:10]
    cur = m.get('price_current_multiplier') or 0
    peak = m.get('price_peak_multiplier') or 0
    print(f"  {m['ticker']:<8} {m['category']:<22} {cur:.1f}x (peak {peak:.1f}x)  baseline={baseline}  탐지={detected}")

# 이슈6: 카테고리별 avg price_current_multiplier
print("\n=== 카테고리별 평균 가격 수익률 ===")
from collections import defaultdict
r6 = client.table('hundredx_category_matches').select('category,price_current_multiplier').is_('exited_at','null').execute()
cat_mults = defaultdict(list)
for m in (r6.data or []):
    if m.get('price_current_multiplier'):
        cat_mults[m['category']].append(m['price_current_multiplier'])
for cat, mults in sorted(cat_mults.items(), key=lambda x: -sum(x[1])/len(x[1])):
    avg = sum(mults)/len(mults)
    mx = max(mults)
    print(f"  {cat:<25} avg={avg:.1f}x  max={mx:.1f}x  n={len(mults)}")
