import os, sys
sys.path.insert(0, 'src')
if sys.stdout.encoding != 'utf-8':
    import io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from dotenv import load_dotenv; load_dotenv()
from supabase import create_client
c = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_KEY'])

# library stocks의 rise_start_date 분포 확인
r = c.table('hundredx_library_stocks').select('ticker,category,rise_start_date,earliest_signal_date').execute()
print("=== library stocks rise_start_date 분포 ===")
dates = []
for row in (r.data or []):
    d = row.get('rise_start_date') or row.get('earliest_signal_date')
    if d:
        dates.append(d[:7])  # YYYY-MM

from collections import Counter
cnt = Counter(dates)
for yr_mo in sorted(cnt.keys()):
    print(f"  {yr_mo}: {cnt[yr_mo]}개")

# 각 library stock에 대해 해당 날짜 이전 공시 수 확인 (샘플 5개)
print("\n=== library stocks 사전 공시 데이터 현황 (샘플) ===")
for row in (r.data or [])[:8]:
    ticker = row['ticker']
    rise = row.get('rise_start_date')
    if not rise:
        continue
    stk = c.table('stocks').select('name_kr').eq('ticker', ticker).execute()
    name = stk.data[0]['name_kr'] if stk.data else ticker

    # 상승 시작 18개월 전부터 상승 시작까지 공시 수
    from datetime import datetime, timedelta
    try:
        rise_dt = datetime.fromisoformat(rise[:10])
        start_dt = rise_dt - timedelta(days=18*30)
        cnt_filings = c.table('filings').select('id', count='exact').eq('ticker', ticker)\
            .gte('filed_at', start_dt.date().isoformat())\
            .lt('filed_at', rise_dt.date().isoformat())\
            .execute()
        cnt_fin = c.table('financials_q').select('fq', count='exact').eq('ticker', ticker).execute()
        print(f"  {name}({ticker}) 상승={rise[:7]} | 사전공시={cnt_filings.count or 0}건 | 재무분기={cnt_fin.count or 0}개")
    except Exception as e:
        print(f"  {name}({ticker}) 오류: {e}")
