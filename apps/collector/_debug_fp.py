import os, sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, 'src')
from dotenv import load_dotenv; load_dotenv()
from supabase import create_client
client = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_KEY'])

# 라이브러리에서 010140 카테고리 확인
lib_res = client.table('hundredx_library_stocks').select(
    'ticker, category, pre_rise_signals'
).eq('ticker', '010140').execute()
print("=== 010140 in library ===")
for r in lib_res.data:
    print(f"  category={r['category']}")
    sig = r.get('pre_rise_signals') or {}
    print(f"  pre_rise_signals keys: {list(sig.keys())}")
    if 'quant' in sig:
        print(f"  quant: {json.dumps(sig['quant'], indent=4, ensure_ascii=False)}")
print()

# 010140 active match 상세
res = client.table('hundredx_category_matches').select(
    'ticker, category, fingerprint_score, fingerprint_dims, analog_ticker'
).eq('ticker', '010140').is_('exited_at', None).execute()

print("=== 010140 active matches ===")
for r in res.data:
    print(f"category={r['category']}, fp={r['fingerprint_score']}, analog={r['analog_ticker']}")
    dims = r.get('fingerprint_dims') or {}
    print(f"  matched: {dims.get('matched', [])}")
    print(f"  missing: {dims.get('missing', [])}")
    details = dims.get('details', {})
    if 'quant' in details:
        print(f"  quant details: {json.dumps(details['quant'], indent=4, ensure_ascii=False)}")
print()

# 공급_병목 라이브러리 종목들의 pre_rise_signals 확인
lib_supply = client.table('hundredx_library_stocks').select(
    'ticker, category, pre_rise_signals'
).eq('category', '공급_병목').execute()
print("=== 공급_병목 library stocks ===")
for r in lib_supply.data:
    sig = r.get('pre_rise_signals') or {}
    quant = sig.get('quant', {})
    print(f"  {r['ticker']}: quant={json.dumps(quant, ensure_ascii=False)}")
