import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv("apps/collector/.env")

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_SERVICE_KEY")
supabase: Client = create_client(url, key)

def count_news():
    res = supabase.table("macro_news").select("*", count="exact").limit(1).execute()
    print(f"Total macro_news: {res.count}")
    
    res = supabase.table("news").select("*", count="exact").limit(1).execute()
    print(f"Total news: {res.count}")

if __name__ == "__main__":
    count_news()
