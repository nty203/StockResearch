from src.upsert import get_client
client = get_client()
res1 = client.table('filings').delete().eq('url', 'https://dart.fss.or.kr/test').execute()
res2 = client.table('filings').delete().eq('url', 'https://dart.fss.or.kr/test2').execute()
print(f"Cleaned up {len(res1.data or []) + len(res2.data or [])} test filings.")
