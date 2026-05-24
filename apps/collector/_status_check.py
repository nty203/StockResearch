"""현재 수집 데이터 기반 업그레이드 요소 분석."""
import os, sys
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv()
from supabase import create_client
from collections import Counter
from datetime import date, timedelta

client = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_KEY'])

# 1. 활성 매칭 카테고리 분포
r = client.table('hundredx_category_matches').select(
    'ticker,category,confidence,first_detected_at,price_current_multiplier,evidence'
).is_('exited_at', 'null').order('confidence', desc=True).limit(200).execute()

matches = r.data or []
print(f"=== 활성 매칭 현황 ===")
cat_cnt = Counter(m['category'] for m in matches)
for cat, cnt in sorted(cat_cnt.items(), key=lambda x: -x[1]):
    cat_matches = [m for m in matches if m['category'] == cat]
    avg_conf = sum(m['confidence'] for m in cat_matches) / len(cat_matches)
    print(f"  {cat:<25} {cnt:>3}개  avg_conf={avg_conf:.3f}")

# 2. 신뢰도 분포
confs = [m['confidence'] for m in matches]
if confs:
    print(f"\n신뢰도: min={min(confs):.3f} avg={sum(confs)/len(confs):.3f} max={max(confs):.3f}")
    high = sum(1 for c in confs if c >= 0.85)
    mid  = sum(1 for c in confs if 0.75 <= c < 0.85)
    low  = sum(1 for c in confs if c < 0.75)
    print(f"  고신뢰(≥0.85): {high}개 | 중(0.75~): {mid}개 | 저(0.70~): {low}개")

# 3. 최근 7일 신규
since = (date.today() - timedelta(days=7)).isoformat()
recent = [m for m in matches if str(m.get('first_detected_at',''))[:10] >= since]
print(f"\n=== 최근 7일 신규 탐지 {len(recent)}개 ===")
for m in sorted(recent, key=lambda x: -x['confidence'])[:15]:
    mult = m.get('price_current_multiplier')
    mult_str = f" | {mult:.1f}x" if mult else ""
    dt = str(m['first_detected_at'])[:10]
    print(f"  [{dt}] {m['ticker']:<8} {m['category']:<25} conf={m['confidence']:.3f}{mult_str}")

# 4. price_current_multiplier NULL 비율 (데이터 품질)
total = len(matches)
null_price = sum(1 for m in matches if not m.get('price_current_multiplier'))
print(f"\n=== 데이터 품질 ===")
print(f"  price_current_multiplier NULL: {null_price}/{total} ({null_price/total*100:.0f}%)" if total else "  No data")

# 5. 고신뢰 탑 종목
print(f"\n=== 상위 15개 (신뢰도순) ===")
for m in sorted(matches, key=lambda x: -x['confidence'])[:15]:
    mult = m.get('price_current_multiplier')
    mult_str = f" | {mult:.1f}x" if mult else ""
    evid = m.get('evidence') or []
    kws = [e.get('keyword') or e.get('text','') for e in evid[:2] if isinstance(e, dict)]
    kw_str = ' / '.join(str(k)[:20] for k in kws if k)
    print(f"  {m['ticker']:<8} {m['category']:<25} {m['confidence']:.3f}{mult_str}  {kw_str}")

# 6. 최근 수집된 공시 (오늘/어제)
since2 = (date.today() - timedelta(days=2)).isoformat()
fr = client.table('filings').select('ticker,headline,filed_at,source,keywords').gte('filed_at', since2).order('filed_at', desc=True).limit(30).execute()
filings = fr.data or []
print(f"\n=== 최근 2일 수집 공시 {len(filings)}건 ===")
for f in filings[:20]:
    kws = (f.get('keywords') or [])[:3]
    kw_str = ','.join(kws) if kws else ''
    print(f"  [{str(f['filed_at'])[:10]}] {f.get('source','?'):<5} {f['ticker']:<8} {(f.get('headline') or '')[:50]}  [{kw_str}]")

# 7. 탐지 못한 종목 힌트 — 공시는 있지만 category_matches 없는 종목
filing_tickers = {f['ticker'] for f in filings if f.get('keywords')}
matched_tickers = {m['ticker'] for m in matches}
undetected = filing_tickers - matched_tickers
if undetected:
    print(f"\n=== 공시 있지만 미탐지 종목 {len(undetected)}개 (업그레이드 후보) ===")
    for t in sorted(undetected)[:10]:
        t_filings = [f for f in filings if f['ticker'] == t]
        for f in t_filings[:1]:
            kws = ','.join((f.get('keywords') or [])[:3])
            print(f"  {t:<8} {(f.get('headline') or '')[:55]}  [{kws}]")
