import os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, 'src')
from dotenv import load_dotenv; load_dotenv()
from supabase import create_client
client = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_KEY'])

res = client.table('hundredx_category_matches').select(
    'ticker, category, fingerprint_score, confidence'
).is_('exited_at', None).order('fingerprint_score', desc=True).execute()

data = res.data or []
has_fp = [r for r in data if r.get('fingerprint_score') and r['fingerprint_score'] > 0]
no_fp = [r for r in data if not r.get('fingerprint_score') or r['fingerprint_score'] == 0]

print(f"Active matches: {len(data)}")
print(f"  With FP score (>0): {len(has_fp)}")
print(f"  Without FP score:   {len(no_fp)}")
print()
print(f"{'Ticker':<10} {'Category':<22} {'FP%':>6} {'Conf':>6}")
print('-' * 50)
for r in data:
    fp = r.get('fingerprint_score') or 0
    fp_str = f"{fp*100:.0f}%" if fp > 0 else '-'
    conf = r.get('confidence', 0)
    print(f"{r['ticker']:<10} {r['category']:<22} {fp_str:>6} {conf:>6.2f}")
