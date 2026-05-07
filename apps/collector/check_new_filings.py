from src.upsert import get_client
from datetime import datetime, timedelta, timezone
client = get_client()
# Look for filings created in the last 10 minutes (during the action run)
since = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
res = client.table('filings').select('ticker, headline, created_at').gte('created_at', since).execute()
print(f"New filings found: {len(res.data or [])}")
for f in (res.data or []):
    print(f"[{f['ticker']}] {f['headline']}")
