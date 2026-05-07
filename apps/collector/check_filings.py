from src.upsert import get_client
client = get_client()
res = client.table('filings').select('ticker, headline, raw_text').eq('ticker', '082740').limit(5).execute()
print(f"Found {len(res.data)} filings for 082740")
for f in res.data:
    print(f"Headline: {f['headline']}")
    print(f"Snippet: {f['raw_text'][:200]}...")
    print("-" * 20)
