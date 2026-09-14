import os
from supabase import create_client, Client
from dotenv import load_dotenv
import json
from datetime import datetime, timedelta

load_dotenv("apps/collector/.env")

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_SERVICE_KEY")
supabase: Client = create_client(url, key)

def fetch_today_news():
    # Get today's date
    today = datetime.utcnow().date().isoformat()
    # Or just fetch top 50 latest news if date might be off
    print("Fetching latest news from macro_news...")
    res = supabase.table("macro_news").select("published_at, title, summary").order("published_at", desc=True).limit(50).execute()
    
    if res.data:
        print(f"Found {len(res.data)} articles. Here are the top 20:")
        for idx, row in enumerate(res.data[:20]):
            print(f"{idx+1}. [{row['published_at']}] {row['title']}")
            if row.get('summary'):
                print(f"   {row['summary'][:150]}...")
        
        with open("scratch/today_news.json", "w", encoding="utf-8") as f:
            json.dump(res.data, f, ensure_ascii=False, indent=2)
            
    else:
        print("No news found.")

if __name__ == "__main__":
    fetch_today_news()
