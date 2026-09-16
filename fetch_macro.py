import os
import urllib.request

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in the environment")

url = f"{SUPABASE_URL}/rest/v1/macro_ideas?id=eq.94e35beb-98cb-4a9a-8959-3a50633fa812&select=*"
headers = {"apikey": SUPABASE_SERVICE_KEY}

req = urllib.request.Request(url, headers=headers)
with urllib.request.urlopen(req) as response:
    data = response.read().decode("utf-8")
    with open("macro_output.json", "w", encoding="utf-8") as f:
        f.write(data)
