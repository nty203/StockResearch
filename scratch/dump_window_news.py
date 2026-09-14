import os
import sys
import json
import urllib.request
from datetime import datetime
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv("apps/collector/.env")

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_KEY")
headers = {
    "apikey": key,
    "Authorization": f"Bearer {key}",
}

start_time_utc = "2026-07-21T11:00:00Z"

def fetch(table):
    req = urllib.request.Request(f"{url}/rest/v1/{table}?select=title,summary,published_at,category,source&published_at=gte.{start_time_utc}&order=published_at.desc&limit=1000", headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"Error fetching {table}: {e}")
        return []

macro_news = fetch("macro_news")

with open("scratch/window_news.json", "w", encoding="utf-8") as f:
    json.dump(macro_news, f, ensure_ascii=False, indent=2)

print(f"Saved {len(macro_news)} items to scratch/window_news.json")
