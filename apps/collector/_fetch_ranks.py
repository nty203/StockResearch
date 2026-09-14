"""Fetch macro_theme_ranks from Supabase and print."""
import os, json, urllib.request
from dotenv import load_dotenv
load_dotenv()

url = os.environ["SUPABASE_URL"]
key = os.environ["SUPABASE_SERVICE_KEY"]

req = urllib.request.Request(
    f"{url}/rest/v1/macro_theme_ranks?select=theme,rank,score,aligned&run_date=eq.2026-07-15&order=rank.asc",
    headers={"apikey": key, "Authorization": f"Bearer {key}"},
)
resp = urllib.request.urlopen(req)
data = json.loads(resp.read())

for r in data:
    print(f"  {r['rank']:>2}. {r['theme']:30s}  score={r['score']:6.1f}  aligned={r['aligned']}")
