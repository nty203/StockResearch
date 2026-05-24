import os, sys, json
sys.path.insert(0, 'src')
if sys.stdout.encoding != 'utf-8':
    import io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from dotenv import load_dotenv; load_dotenv()
from supabase import create_client
c = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_KEY'])

r = c.table('hundredx_library_stocks').select('ticker,category,pre_rise_signals,earliest_signal_date,triggers').execute()
empty = 0
populated = 0
print("=== pre_rise_signals 현황 ===")
for row in (r.data or []):
    ps = row.get('pre_rise_signals') or {}
    has_data = bool(ps.get('keywords') or ps.get('quant') or ps.get('sector_required'))
    stk = c.table('stocks').select('name_kr').eq('ticker', row['ticker']).execute()
    name = stk.data[0]['name_kr'] if stk.data else row['ticker']
    cat = row['category']
    if has_data:
        populated += 1
        dims = list(ps.keys())
        print(f"  O {name}({row['ticker']}) {cat} -> dims={dims}")
    else:
        empty += 1
        print(f"  X {name}({row['ticker']}) {cat} -> EMPTY")

print(f"\n결과: 비어있음={empty} / 데이터있음={populated} / 전체={empty+populated}")

# triggers 현황도 확인 (extract_signals의 다른 출력)
print("\n=== triggers 현황 ===")
has_triggers = sum(1 for row in (r.data or []) if row.get('triggers'))
print(f"  triggers 있음: {has_triggers}/{len(r.data or [])}")
