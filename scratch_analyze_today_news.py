import os
import sys
import json
import urllib.request
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv("apps/collector/.env")

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_KEY")
headers = {
    "apikey": key,
    "Authorization": f"Bearer {key}",
}

def fetch(table, limit=200):
    req = urllib.request.Request(f"{url}/rest/v1/{table}?select=*&order=published_at.desc&limit={limit}", headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"Error fetching {table}: {e}")
        return []

macro_news = fetch("macro_news", 200)

with open("scratch/macro_news_recent.txt", "w", encoding="utf-8") as f:
    for idx, m in enumerate(macro_news, 1):
        pub = m.get("published_at", "")[:19]
        src = m.get("source", "")
        cat = m.get("category", "")
        title = m.get("title", "")
        summary = m.get("summary", "")
        f.write(f"{idx}. [{pub}] [{cat}] [{src}] {title}\n")
        if summary:
            f.write(f"   Summary: {summary}\n")
