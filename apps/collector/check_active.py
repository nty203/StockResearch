from src.upsert import get_client
client = get_client()
res = client.table('hundredx_category_matches').select('ticker, category, confidence, evidence').is_('exited_at', 'null').execute()
print(f"Active matches: {len(res.data or [])}")
for r in (res.data or []):
    print(f"[{r['ticker']}] {r['category']} (Conf: {r['confidence']})")
