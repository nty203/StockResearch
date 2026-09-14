import os
import sys
from supabase import create_client, Client
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv(".env")
load_dotenv("apps/collector/.env")

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_SERVICE_KEY")
supabase: Client = create_client(url, key)

def check_ideas():
    print("Checking macro_ideas table...")
    res = supabase.table("macro_ideas").select("date", "theme", "title", "total_score").order("date", desc=True).limit(10).execute()
    if res.data:
        for row in res.data:
            print(f"[{row['date']}] [Score: {row['total_score']}] {row['theme']} - {row['title']}")
    else:
        print("No ideas found in macro_ideas table.")

if __name__ == "__main__":
    check_ideas()
