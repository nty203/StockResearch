"""Fetch recent macro_news - items 1-70 (newest) with compact format."""
import os, json, urllib.request
from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv()

url = os.environ["SUPABASE_URL"]
key = os.environ["SUPABASE_SERVICE_KEY"]
since = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%dT00:00:00Z")

endpoint = f"{url}/rest/v1/macro_news?select=title,summary,category,published_at,source&published_at=gte.{since}&order=published_at.desc&limit=400"
req = urllib.request.Request(endpoint, headers={"apikey": key, "Authorization": f"Bearer {key}"})
resp = urllib.request.urlopen(req)
data = json.loads(resp.read())

print(f"Total: {len(data)} | Range: {data[-1]['published_at'][:10]} ~ {data[0]['published_at'][:10]}\n")

# Items 1-70 only
for i, r in enumerate(data[:70]):
    dt = r.get("published_at", "")[:16]
    cat = r.get("category", "")
    title = r.get("title", "")[:80]
    print(f"[{i+1}] [{dt}] [{cat}] {title}")
