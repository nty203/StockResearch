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

def fetch(table):
    req = urllib.request.Request(f"{url}/rest/v1/{table}?select=title,summary,published_at,category&order=published_at.desc&limit=100", headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"Error fetching {table}: {e}")
        return []

macro_news = fetch("macro_news")
news = fetch("news")

with open("scratch_news.txt", "w", encoding="utf-8") as f:
    f.write("=== MACRO NEWS ===\n")
    for item in macro_news:
        f.write(f"[{item.get('published_at')}] [{item.get('category')}] {item.get('title')}\n")
        if item.get('summary'):
            f.write(f"  Summary: {item.get('summary')}\n")
    
    f.write("\n=== COMPANY NEWS ===\n")
    for item in news:
        f.write(f"[{item.get('published_at')}] {item.get('title')}\n")
        if item.get('summary'):
            f.write(f"  Summary: {item.get('summary')}\n")
print("Saved to scratch_news.txt")
