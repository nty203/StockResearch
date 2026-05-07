from src.upsert import get_client
client = get_client()
tickers = ['082740', '017510', '083450', '042700']
res = client.table('hundredx_category_matches').delete().in_('ticker', tickers).execute()
print(f"Deleted {len(res.data or [])} manual entries.")
