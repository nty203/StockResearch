from src.upsert import get_client
client = get_client()
res = client.table('settings').upsert({'key': 'filings_lookback_days', 'value_json': '60'}).execute()
print("Updated filings_lookback_days to 60.")
