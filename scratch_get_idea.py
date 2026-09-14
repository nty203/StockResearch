import os
import json
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv(".env")
load_dotenv("apps/collector/.env")
load_dotenv("apps/web/.env.local")

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_SERVICE_KEY")
supabase: Client = create_client(url, key)

def get_idea(idea_id):
    res = supabase.table("macro_ideas").select("*").eq("id", idea_id).execute()
    if res.data:
        with open("scratch_idea.json", "w", encoding="utf-8") as f:
            json.dump(res.data[0], f, indent=2, ensure_ascii=False)
        print("Success")
    else:
        print("Not found")

if __name__ == "__main__":
    import sys
    idea_id = sys.argv[1] if len(sys.argv) > 1 else "3138eea7-0ced-4980-8c05-1bf34ab0805f"
    get_idea(idea_id)
