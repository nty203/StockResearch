import os, sys
sys.path.insert(0, 'src')
if sys.stdout.encoding != 'utf-8':
    import io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from dotenv import load_dotenv; load_dotenv()
from supabase import create_client
c = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_KEY'])

# 1. prices_daily 컬럼
r = c.table('prices_daily').select('*').eq('ticker','042700').order('date',desc=True).limit(1).execute()
if r.data:
    print('=== prices_daily 컬럼 ===')
    print(list(r.data[0].keys()))
    print({k: r.data[0].get(k) for k in ['date','close','market_cap','shares_outstanding','volume']})

# 2. library stocks → stocks.sector_tag 현황
lib_r = c.table('hundredx_library_stocks').select('ticker,category').execute()
lib_tickers = list({row['ticker'] for row in (lib_r.data or [])})
print(f'\n=== library stocks {len(lib_tickers)}개 sector_tag 현황 ===')
empty_sector = 0
for ticker in lib_tickers[:20]:
    stk = c.table('stocks').select('name_kr,sector_tag').eq('ticker', ticker).execute()
    if stk.data:
        name = stk.data[0]['name_kr']
        sector = stk.data[0].get('sector_tag')
        if not sector:
            empty_sector += 1
        print(f"  {name}({ticker}) sector_tag={sector}")
print(f'  → sector_tag 없음: {empty_sector}/{len(lib_tickers[:20])}')

# 3. active matches 중 library stock 겹침 (한미반도체가 가장 중요)
active_r = c.table('hundredx_category_matches').select('ticker,category,confidence').is_('exited_at','null').execute()
lib_ticker_set = set(lib_tickers)
overlap = [row for row in (active_r.data or []) if row['ticker'] in lib_ticker_set]
print(f'\n=== library stock이면서 active match인 것들 ({len(overlap)}개) ===')
for row in overlap:
    stk = c.table('stocks').select('name_kr').eq('ticker',row['ticker']).execute()
    name = stk.data[0]['name_kr'] if stk.data else row['ticker']
    print(f"  {name}({row['ticker']}) → {row['category']} conf={row['confidence']}")
