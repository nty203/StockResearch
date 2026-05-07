from src.upsert import get_client
client = get_client()
tickers = ['082740', '017510', '083450', '042700']
for t in tickers:
    news = client.table('news').select('id').eq('ticker', t).limit(1).execute()
    reports = client.table('reports').select('id').eq('ticker', t).limit(1).execute()
    print(f"[{t}] News: {len(news.data)}, Reports: {len(reports.data)}")
