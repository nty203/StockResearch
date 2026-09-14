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

# 2026-08-11 20:00 KST = 2026-08-11 11:00:00 UTC
start_time_utc = "2026-08-11T11:00:00Z"

def fetch_table(table, min_time=None, limit=500):
    query = f"{url}/rest/v1/{table}?select=*&order=published_at.desc&limit={limit}"
    if min_time:
        query = f"{url}/rest/v1/{table}?select=*&published_at=gte.{min_time}&order=published_at.desc&limit={limit}"
    req = urllib.request.Request(query, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        print(f"Error fetching {table}: {e}")
        return []

macro_news = fetch_table("macro_news", start_time_utc)
news = fetch_table("news", start_time_utc)

print(f"Macro news since {start_time_utc}: {len(macro_news)}")
print(f"Company news since {start_time_utc}: {len(news)}")

if len(macro_news) < 15:
    print("Fetching top 200 latest macro news regardless of cutoff...")
    macro_news = fetch_table("macro_news", limit=200)

if len(news) < 15:
    print("Fetching top 200 latest company news regardless of cutoff...")
    news = fetch_table("news", limit=200)

print(f"Total macro_news items loaded: {len(macro_news)}")
print(f"Total news items loaded: {len(news)}")

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
