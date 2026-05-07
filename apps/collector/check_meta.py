from src.upsert import get_client
client = get_client()
tickers=['082740', '017510', '083450', '042700', '053080']
res=client.table('stocks').select('ticker, name_kr').in_('ticker', tickers).execute()
print(res.data)
