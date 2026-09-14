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
    cur.execute("SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid = 'macro_ideas'::regclass;")
    rows = cur.fetchall()
    print("Constraints found:")
    for row in rows:
        print(f"  Name: {row[0]}")
        print(f"  Def: {row[1]}")
    conn.close()
except Exception as e:
    print("Error:", e)
