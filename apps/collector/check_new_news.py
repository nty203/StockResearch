from src.upsert import get_client
from datetime import datetime, timedelta, timezone
client = get_client()
since = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
res = client.table('news').select('ticker, title, created_at').gte('created_at', since).execute()
print(f"New news found: {len(res.data or [])}")
for n in (res.data or []):
    print(f"[{n['ticker']}] {n['title']}")
