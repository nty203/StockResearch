import os
import json
import urllib.request
from dotenv import load_dotenv

load_dotenv('apps/collector/.env')
url = os.environ.get('SUPABASE_URL')
key = os.environ.get('SUPABASE_SERVICE_KEY')

headers = {
    'apikey': key,
    'Authorization': f'Bearer {key}'
}

# 2026-08-13T11:00:00Z (20:00 KST)
start_time_utc = "2026-08-13T11:00:00Z"

req1 = urllib.request.Request(f'{url}/rest/v1/macro_news?select=*&published_at=gte.{start_time_utc}&order=published_at.desc&limit=500', headers=headers)
try:
    with urllib.request.urlopen(req1) as resp:
        macro_news = json.loads(resp.read().decode('utf-8'))
except Exception as e:
    print('Error macro_news window:', e)
    macro_news = []

if len(macro_news) < 10:
    print('Window macro_news < 10, fetching latest 200 macro_news...')
    req1_all = urllib.request.Request(f'{url}/rest/v1/macro_news?select=*&order=published_at.desc&limit=200', headers=headers)
    with urllib.request.urlopen(req1_all) as resp:
        macro_news = json.loads(resp.read().decode('utf-8'))

req2 = urllib.request.Request(f'{url}/rest/v1/news?select=*&published_at=gte.{start_time_utc}&order=published_at.desc&limit=500', headers=headers)
try:
    with urllib.request.urlopen(req2) as resp:
        news = json.loads(resp.read().decode('utf-8'))
except Exception as e:
    print('Error news window:', e)
    news = []

if len(news) < 10:
    print('Window news < 10, fetching latest 200 news...')
    req2_all = urllib.request.Request(f'{url}/rest/v1/news?select=*&order=published_at.desc&limit=200', headers=headers)
    with urllib.request.urlopen(req2_all) as resp:
        news = json.loads(resp.read().decode('utf-8'))

print(f'Fetched {len(macro_news)} macro_news, {len(news)} company news')

with open('scratch_fetched_news.json', 'w', encoding='utf-8') as f:
    json.dump({'macro_news': macro_news, 'news': news}, f, ensure_ascii=False, indent=2)

with open('scratch_news.txt', 'w', encoding='utf-8') as f:
    f.write(f'=== MACRO NEWS ({len(macro_news)} items) ===\n')
    for m in macro_news:
        pub = m.get("published_at", "")
        cat = m.get("category", "")
        src = m.get("source", "")
        t = m.get("title", "")
        s = m.get("summary", "")
        f.write(f'[{pub}] [{cat}] [{src}] {t}\n')
        if s:
            f.write(f'  Summary: {s}\n')
    f.write(f'\n=== COMPANY NEWS ({len(news)} items) ===\n')
    for n in news:
        pub = n.get("published_at", "")
        tk = n.get("ticker", "")
        t = n.get("title", "")
        s = n.get("summary", "")
        f.write(f'[{pub}] [{tk}] {t}\n')
        if s:
            f.write(f'  Summary: {s}\n')

print("Saved scratch_fetched_news.json and scratch_news.txt")
