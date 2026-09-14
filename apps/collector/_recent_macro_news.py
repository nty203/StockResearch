import sys, os
sys.stdout.reconfigure(encoding='utf-8')
import json, urllib.request, datetime

supabase_url = os.environ["SUPABASE_URL"]
supabase_key = os.environ["SUPABASE_SERVICE_KEY"]
headers = {
    "apikey": supabase_key,
    "Authorization": f"Bearer {supabase_key}",
}

# 최근 3일 뉴스 조회 (신선한 트리거 우선)
since = (datetime.date.today() - datetime.timedelta(days=3)).isoformat()
url = f"{supabase_url}/rest/v1/macro_news?select=title,summary,category,published_at,source&published_at=gte.{since}T00:00:00Z&order=published_at.desc&limit=200"
req = urllib.request.Request(url, headers=headers)
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read())

print(f"최근 3일 macro_news: {len(data)}건")
print("=" * 80)
for item in data[:80]:
    dt = item.get('published_at', '')[:10]
    cat = item.get('category', '')
    title = item.get('title', '')
    summary = (item.get('summary') or '')[:100]
    print(f"[{dt}][{cat}] {title}")
    if summary:
        print(f"  └ {summary}")
