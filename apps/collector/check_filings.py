import os, json, urllib.request, sys
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv
from datetime import date, timedelta

load_dotenv('.env')
url = os.environ['SUPABASE_URL']
key = os.environ['SUPABASE_SERVICE_KEY']
since7 = (date.today() - timedelta(days=7)).isoformat()

def fetch(endpoint):
    req = urllib.request.Request(endpoint, headers={'apikey': key, 'Authorization': f'Bearer {key}'})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

filings = fetch(f"{url}/rest/v1/filings?select=*&filed_at=gte.{since7}T00:00:00Z&order=filed_at.desc&limit=3")
print(f"=== 공시 스키마 확인 ({len(filings)}건) ===")
if filings:
    print("컬럼:", list(filings[0].keys()))
    for f in filings[:3]:
        print(f)
