import os, sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, 'src')
from dotenv import load_dotenv; load_dotenv()
from supabase import create_client
client = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_KEY'])

res = client.table('hundredx_library_stocks').select('ticker, category, pre_rise_signals').execute()
print('sector_required 설정 현황:')
no_sector = 0
has_sector = 0
for r in res.data:
    sig = r.get('pre_rise_signals') or {}
    sector = sig.get('sector_required')
    has_quant = bool(sig.get('quant'))
    if sector:
        has_sector += 1
        print(f'  {r["ticker"]} / {r["category"]}: sector={sector}')
    else:
        no_sector += 1

print()
print(f'sector_required 있음: {has_sector}개')
print(f'sector_required 없음 (크로스-섹터 매칭 위험): {no_sector}개')
print()

# stocks 테이블에서 각 라이브러리 종목의 실제 sector_tag 확인
tickers = list(set(r['ticker'] for r in res.data))
stocks_res = client.table('stocks').select('ticker, sector_tag').in_('ticker', tickers).execute()
sector_map = {s['ticker']: s.get('sector_tag') for s in stocks_res.data}

print('실제 sector_tag (from stocks table):')
for r in sorted(res.data, key=lambda x: x['category']):
    actual = sector_map.get(r['ticker'], 'N/A')
    sig = r.get('pre_rise_signals') or {}
    stored = sig.get('sector_required', '-')
    mismatch = '⚠️' if stored == '-' and actual else ''
    print(f'  {r["ticker"]} / {r["category"]}: actual={actual}, stored={stored} {mismatch}')
