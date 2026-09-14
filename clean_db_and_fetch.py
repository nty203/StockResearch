import os
import urllib.request
from dotenv import load_dotenv

load_dotenv("apps/collector/.env")
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_KEY")
headers = {
    "apikey": key,
    "Authorization": f"Bearer {key}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

# Delete macro_ideas for today
from datetime import datetime, timezone, timedelta
kst = timezone(timedelta(hours=9))
today_str = datetime.now(kst).strftime("%Y-%m-%d")

print(f"Deleting today's macro_ideas ({today_str})...")
req = urllib.request.Request(f"{url}/rest/v1/macro_ideas?date=eq.{today_str}", headers=headers, method='DELETE')
try:
    with urllib.request.urlopen(req) as response:
        print("Deleted macro_ideas:", response.getcode())
except Exception as e:
    print("Error deleting macro_ideas:", e)

# Delete stale English news from macro_news
print("Deleting stale English news (lang=en) from macro_news...")
req = urllib.request.Request(f"{url}/rest/v1/macro_news?lang=eq.en", headers=headers, method='DELETE')
try:
    with urllib.request.urlopen(req) as response:
        print("Deleted stale English news:", response.getcode())
except Exception as e:
    print("Error deleting English news:", e)

# Also delete from 'news'
req = urllib.request.Request(f"{url}/rest/v1/news?lang=eq.en", headers=headers, method='DELETE')
try:
    with urllib.request.urlopen(req) as response:
        pass
except Exception as e:
    pass

# Fetch the real top 30 news
import json
req = urllib.request.Request(f"{url}/rest/v1/macro_news?select=title,summary,category,published_at,source&order=published_at.desc&limit=30", headers=headers)
try:
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode('utf-8'))
        print("\n--- Real Top 30 Latest News ---")
        for i, row in enumerate(data):
            print(f"{i+1}. [{row.get('published_at')[:10]}] [{row.get('category')}] {row.get('title')}")
except Exception as e:
    print("Error fetching news:", e)
