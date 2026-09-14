import os
import sys
import json
import urllib.request
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv("apps/collector/.env")

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_KEY")
headers = {
    "apikey": key,
    "Authorization": f"Bearer {key}",
}

start_time_utc = "2026-08-11T11:00:00Z"

def fetch(table):
    req = urllib.request.Request(f"{url}/rest/v1/{table}?select=*&published_at=gte.{start_time_utc}&order=published_at.desc&limit=500", headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"Error fetching {table}: {e}")
        return []

macro_news = fetch("macro_news")
news = fetch("news")

# If window count is small, also fetch latest 100 items from macro_news regardless of timestamp to inspect latest available data
if len(macro_news) < 10:
    print("Window news count < 10, fetching latest 100 items from macro_news for broader context...")
    req = urllib.request.Request(f"{url}/rest/v1/macro_news?select=*&order=published_at.desc&limit=100", headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            macro_news = json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        print(f"Error fetching broad macro_news: {e}")

print(f"Macro news retrieved: {len(macro_news)}")
print(f"Company news retrieved: {len(news)}")

with open("scratch_news.txt", "w", encoding="utf-8") as f:
    f.write(f"=== MACRO NEWS ({len(macro_news)} items) ===\n")
    for item in macro_news:
        pub = item.get("published_at")
        cat = item.get("category", "")
        src = item.get("source", "")
        title = item.get("title", "")
        summary = item.get("summary", "")
        f.write(f"[{pub}] [{cat}] [{src}] {title}\n")
        if summary:
            f.write(f"  Summary: {summary}\n")
            
    f.write(f"\n=== COMPANY NEWS ({len(news)} items) ===\n")
    for item in news:
        pub = item.get("published_at")
        title = item.get("title", "")
        summary = item.get("summary", "")
        f.write(f"[{pub}] {title}\n")
        if summary:
            f.write(f"  Summary: {summary}\n")

with open("scratch_fetched_news.json", "w", encoding="utf-8") as f:
    json.dump({"macro_news": macro_news, "news": news}, f, ensure_ascii=False, indent=2)

print("Saved to scratch_fetched_news.json and scratch_news.txt")
