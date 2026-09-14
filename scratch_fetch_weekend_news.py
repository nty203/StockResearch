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

# 2026-07-17 20:00:00 KST = 2026-07-17 11:00:00 UTC
start_time_utc = "2026-07-17T11:00:00Z"

def fetch(table):
    req = urllib.request.Request(f"{url}/rest/v1/{table}?select=title,published_at,category,source&published_at=gte.{start_time_utc}&order=published_at.desc&limit=1000", headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"Error fetching {table}: {e}")
        return []

macro_news = fetch("macro_news")

kst = timezone(timedelta(hours=9))

output_file = "scratch_weekend_news.txt"
with open(output_file, "w", encoding="utf-8") as f:
    f.write(f"--- 전일 장마감(금요일 오후 8시 KST) 이후 수집된 매크로 뉴스 리스트 (총 {len(macro_news)}건) ---\n")
    for item in macro_news:
        pub_utc = datetime.fromisoformat(item.get('published_at').replace('Z', '+00:00'))
        pub_kst = pub_utc.astimezone(kst).strftime("%Y-%m-%d %H:%M")
        cat = item.get('category', '기타') or '기타'
        src = item.get('source', '') or ''
        title = item.get('title', '')
        f.write(f"[{pub_kst}] [{cat}] {title} ({src})\n")

print(f"Saved {len(macro_news)} news items to {output_file}")
