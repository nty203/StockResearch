import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
from dotenv import load_dotenv
load_dotenv()
from supabase import create_client
client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

print("### PPTR Rule Matches Table ###")
m = client.table("pptr_rule_matches").select("*").limit(5).execute()
print(f"Sample matches: {len(m.data)}")
for row in m.data:
    print(row)

print("\n### PPTR Rule Near Misses Table ###")
nm = client.table("pptr_rule_near_misses").select("*").limit(5).execute()
print(f"Sample near misses: {len(nm.data)}")
for row in nm.data:
    print(row)
