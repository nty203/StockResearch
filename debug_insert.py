import os
import sys
import json
import urllib.request
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv("apps/collector/.env")

supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")

headers = {
    "apikey": supabase_key,
    "Authorization": f"Bearer {supabase_key}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

from insert_today_ideas_v5 import ideas

for idx, idea in enumerate(ideas):
    data_bytes = json.dumps([idea], ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(f"{supabase_url}/rest/v1/macro_ideas", data=data_bytes, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req) as resp:
            print(f"Idea {idx+1} success!")
    except urllib.error.HTTPError as e:
        print(f"Idea {idx+1} failed with code {e.code}:")
        print(e.read().decode('utf-8'))
