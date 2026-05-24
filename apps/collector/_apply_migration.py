"""Apply migration directly via Supabase RPC."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv()
import psycopg2

db_url = os.environ.get("SUPABASE_DB_URL", "")
if not db_url:
    print("SUPABASE_DB_URL not set")
    sys.exit(1)

sql = """
-- source CHECK 확장
ALTER TABLE filings DROP CONSTRAINT IF EXISTS filings_source_check;
ALTER TABLE filings ADD CONSTRAINT filings_source_check CHECK (source IN ('DART', 'SEC', 'KIND', 'SEED'));

-- unique constraint for upsert
ALTER TABLE filings DROP CONSTRAINT IF EXISTS filings_ticker_filed_at_type_key;
ALTER TABLE filings ADD CONSTRAINT filings_ticker_filed_at_type_key UNIQUE (ticker, filed_at, filing_type);
"""

print("Applying migration...")
try:
    conn = psycopg2.connect(db_url)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(sql)
    print("Migration applied successfully!")

    # Verify
    cur.execute("""
        SELECT constraint_name, constraint_type
        FROM information_schema.table_constraints
        WHERE table_name = 'filings'
        ORDER BY constraint_type, constraint_name
    """)
    rows = cur.fetchall()
    print("\nfilings constraints:")
    for r in rows:
        print(f"  {r[1]:<15} {r[0]}")

    conn.close()
except Exception as e:
    print(f"Error: {e}")
    import traceback; traceback.print_exc()
