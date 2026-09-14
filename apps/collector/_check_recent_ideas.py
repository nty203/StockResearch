import sys, os
sys.stdout.reconfigure(encoding='utf-8')
import json, urllib.request, datetime

supabase_url = os.environ["SUPABASE_URL"]
supabase_key = os.environ["SUPABASE_SERVICE_KEY"]
headers = {
    "apikey": supabase_key,
    "Authorization": f"Bearer {supabase_key}",
}

since7 = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
url = f"{supabase_url}/rest/v1/macro_ideas?select=theme,title,date&date=gte.{since7}&order=date.desc"
req = urllib.request.Request(url, headers=headers)
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read())

print(f"최근 7일 생성된 가설 {len(data)}개:")
seen = set()
for x in data:
    print(f"  [{x['date']}] {x['theme']} — {x['title'][:50]}")
    seen.add(x['theme'])
print(f"\n이미 사용된 테마: {seen}")
print("\n→ 위 테마들과 겹치지 않으면서 실시간 뉴스 트리거가 발생한 상위 테마들을 개수 제한 없이 전부 선별해 가설을 각각 도출할 것")
