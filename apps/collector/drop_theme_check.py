import os
import psycopg2
from dotenv import load_dotenv

load_dotenv(".env")
load_dotenv("apps/collector/.env")

db_url = os.environ.get("SUPABASE_DB_URL")
print(f"Connecting to: {db_url}")

try:
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    
    # 1. Drop check constraint from macro_ideas table
    print("Dropping constraint macro_ideas_theme_check...")
    cur.execute("ALTER TABLE macro_ideas DROP CONSTRAINT IF EXISTS macro_ideas_theme_check;")
    
    conn.commit()
    print("Successfully dropped theme check constraint from macro_ideas!")
    conn.close()
except Exception as e:
    print("Error:", e)
