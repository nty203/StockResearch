import os
from dotenv import load_dotenv
load_dotenv()
import psycopg2
conn = psycopg2.connect(os.environ['SUPABASE_DB_URL'])
cur = conn.cursor()
cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='financials_q' ORDER BY ordinal_position LIMIT 20")
for r in cur.fetchall():
    print(r)
# 샘플 데이터
cur.execute("SELECT * FROM financials_q WHERE ticker='180640' LIMIT 3")
rows = cur.fetchall()
if rows:
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='financials_q' ORDER BY ordinal_position LIMIT 20")
    cols = [r[0] for r in cur.fetchall()]
    print('\nCols:', cols)
    for r in rows:
        print(dict(zip(cols, r)))
conn.close()
