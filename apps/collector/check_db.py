from src.upsert import get_client
client = get_client()

# 1. Library stocks 현황
lib_res = client.table('hundredx_library_stocks').select('*').execute()
lib = lib_res.data or []
print('=== LIBRARY STOCKS ===')
# Show available columns first
if lib:
    print('  Columns:', list(lib[0].keys()))
for r in lib:
    signals = r.get('pre_rise_signals') or {}
    has_quant = bool(signals.get('quant'))
    has_kw = bool(signals.get('keywords'))
    ticker = r.get('ticker','?')
    name = r.get('name') or r.get('name_kr') or r.get('company_name') or '?'
    cat = r.get('category','미분류')
    peak = r.get('peak_multiplier','?')
    rise = r.get('rise_start_date','?')
    quant_keys = list((signals.get('quant') or {}).keys())
    kw_count = len(signals.get('keywords') or [])
    print(f'  [{ticker}] {name} | {cat} | {peak}x | rise:{rise} | quant:{quant_keys} | kw:{kw_count}')

print()

# 2. Active matches 현황
matches = client.table('hundredx_category_matches').select(
    'ticker,category,confidence,first_detected_at,exited_at,fingerprint_score'
).is_('exited_at', 'null').order('confidence', desc=True).limit(50).execute().data or []
print(f'=== ACTIVE MATCHES ({len(matches)} total) ===')
from collections import Counter
cat_counter = Counter()
for m in matches:
    cat_counter[m['category']] += 1

print('  Category distribution:')
for cat, cnt in cat_counter.most_common():
    print(f'    {cat}: {cnt}')

print()
print('  Top 20 by confidence:')
for m in matches[:20]:
    fp = m.get('fingerprint_score')
    fp_str = f' fp:{fp:.2f}' if fp else ''
    ticker = m.get('ticker','?')
    cat = m.get('category','?')
    conf = m.get('confidence', 0)
    fda = (m.get('first_detected_at') or '')[:10]
    print(f'  [{ticker}] {cat} | conf:{conf:.2f}{fp_str} | since:{fda}')

print()

# 3. 재무 데이터 커버리지
target_tickers = ['272210', '077970', '329180', '064350']
ticker_names = {
    '272210': '한화엔진', '077970': 'STX엔진', '329180': 'HD현대중공업', '064350': '현대로템',
}
print('=== KEY TICKER DB CHECK ===')
for t in target_tickers:
    fin = client.table('financials_q').select('ticker,fq,revenue,op_income,op_margin,order_backlog').eq('ticker', t).order('fq', desc=True).limit(4).execute().data or []
    fil = client.table('filings').select('ticker,headline,filed_at').eq('ticker', t).order('filed_at', desc=True).limit(3).execute().data or []
    nm = ticker_names.get(t, t)
    print(f'  [{t}] {nm}: {len(fin)} fin rows, {len(fil)} recent filings')
    for f in fin[:2]:
        print(f'    fin: {f.get("fq")} rev:{f.get("revenue")} opm:{f.get("op_margin")} backlog:{f.get("order_backlog")}')
    for f in fil[:2]:
        hl = (f.get("headline") or "")[:80]
        dt = (f.get("filed_at") or "")[:10]
        print(f'    filing: {dt} {hl}')

print()
total_filings = client.table('filings').select('ticker', count='exact').execute()
print(f'=== TOTAL FILINGS: {total_filings.count} ===')

recent = client.table('filings').select('ticker,headline,filed_at').order('filed_at', desc=True).limit(10).execute().data or []
print('=== RECENT 10 FILINGS ===')
for f in recent:
    hl = (f.get("headline") or "")[:100]
    dt = (f.get("filed_at") or "")[:10]
    print(f'  [{f.get("ticker")}] {dt} | {hl}')
