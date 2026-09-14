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
headers = {"apikey": key, "Authorization": f"Bearer {key}"}

# Cutoff: 2026-07-31T11:00:00Z (20:00 KST on July 31)
start_time_utc = "2026-07-31T11:00:00Z"

def fetch_all(table):
    req = urllib.request.Request(f"{url}/rest/v1/{table}?select=*&published_at=gte.{start_time_utc}&order=published_at.desc&limit=1000", headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        print(f"Error fetching {table}: {e}")
        return []

macro = fetch_all("macro_news")
comp = fetch_all("news")

if len(macro) < 10:
    print(f"Only {len(macro)} macro news since cutoff. Fetching latest 200 items...")
    req = urllib.request.Request(f"{url}/rest/v1/macro_news?select=*&order=published_at.desc&limit=200", headers=headers)
    with urllib.request.urlopen(req) as resp:
        macro = json.loads(resp.read().decode('utf-8'))

if len(comp) < 10:
    print(f"Only {len(comp)} company news since cutoff. Fetching latest 200 items...")
    req = urllib.request.Request(f"{url}/rest/v1/news?select=*&order=published_at.desc&limit=200", headers=headers)
    with urllib.request.urlopen(req) as resp:
        comp = json.loads(resp.read().decode('utf-8'))

print(f"Fetched {len(macro)} macro news and {len(comp)} company news.")

output_data = {"macro_news": macro, "news": comp}
with open("scratch_fetched_news.json", "w", encoding="utf-8") as f:
    json.dump(output_data, f, ensure_ascii=False, indent=2)

with open("scratch_news.txt", "w", encoding="utf-8") as f:
    f.write(f"=== MACRO NEWS ({len(macro)} items) ===\n")
    for m in macro:
        pub = m.get('published_at', '')
        cat = m.get('category', '')
        src = m.get('source', '')
        title = m.get('title', '')
        summary = m.get('summary', '')
        f.write(f"[{pub}] [{cat}] [{src}] {title}\n")
        if summary:
            f.write(f"  Summary: {summary}\n")
            
    f.write(f"\n=== COMPANY NEWS ({len(comp)} items) ===\n")
    for c in comp:
        pub = c.get('published_at', '')
        title = c.get('title', '')
        summary = c.get('summary', '')
        f.write(f"[{pub}] {title}\n")
        if summary:
            f.write(f"  Summary: {summary}\n")

print("Saved scratch_fetched_news.json and scratch_news.txt")
