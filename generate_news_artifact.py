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

start_time_utc = "2026-07-18T11:00:00Z"

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
out_path = r"C:\Users\tzero\.gemini\antigravity\brain\f2cb9a51-2b56-4ca2-9a2b-d03c903e709a\accumulated_news.md"

with open(out_path, "w", encoding="utf-8") as f:
    f.write(f"# 전일 장마감(20:00) 이후 수집된 매크로 뉴스 (총 {len(macro_news)}건)\n\n")
    f.write("| 시간 (KST) | 카테고리 | 출처 | 제목 |\n")
    f.write("|---|---|---|---|\n")
    for item in macro_news:
        pub_utc = datetime.fromisoformat(item.get('published_at').replace('Z', '+00:00'))
        pub_kst = pub_utc.astimezone(kst).strftime("%Y-%m-%d %H:%M")
        cat = item.get('category', '기타') or '기타'
        src = item.get('source', '') or ''
        title = item.get('title', '').replace('|', '&#124;')
        f.write(f"| {pub_kst} | {cat} | {src} | {title} |\n")

print(f"Saved {len(macro_news)} news to {out_path}")
