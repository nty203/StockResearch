import os, json, urllib.request
from datetime import datetime, timedelta

url = os.environ['SUPABASE_URL'] + '/rest/v1/macro_news?select=title,summary,category,published_at,source&order=published_at.desc&limit=200'
since = (datetime.utcnow() - timedelta(days=10)).strftime('%Y-%m-%d')
url += '&published_at=gte.' + since + 'T00:00:00Z'

req = urllib.request.Request(url, headers={
    'apikey': os.environ['SUPABASE_SERVICE_KEY'], 
    'Authorization': 'Bearer ' + os.environ['SUPABASE_SERVICE_KEY']
})

try:
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode('utf-8'))
        with open('news_output.txt', 'w', encoding='utf-8') as f:
            f.write(f'Fetched {len(data)} news items.\n')
            for item in data[:50]:
                f.write(f"[{item.get('published_at')}] [{item.get('category')}] {item.get('title')}\n")
                f.write(f"  {item.get('summary')}\n")
                f.write("---\n")
except Exception as e:
    print(e)
