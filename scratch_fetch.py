import os
import json
from supabase import create_client, Client
from dotenv import load_dotenv

# Try loading from various env files
load_dotenv(".env")
load_dotenv("apps/collector/.env")
load_dotenv("apps/web/.env")
load_dotenv("apps/web/.env.local")

url: str = os.environ.get("SUPABASE_URL") or os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
key: str = os.environ.get("SUPABASE_SERVICE_KEY")
if not url or not key:
    print(f"Error: SUPABASE_URL={url}, SUPABASE_SERVICE_KEY={'set' if key else 'not set'}")
    exit(1)

supabase: Client = create_client(url, key)

def get_idea(idea_id):
    res = supabase.table("macro_ideas").select("*").eq("id", idea_id).execute()
    if res.data:
        with open("scratch_idea.json", "w", encoding="utf-8") as f:
            json.dump(res.data[0], f, indent=2, ensure_ascii=False)
        print("Success")
    else:
        print(f"Not found: {idea_id}")

if __name__ == "__main__":
    get_idea("4d01c1c2-3bf4-4298-b9fc-7e5914b43d28")
