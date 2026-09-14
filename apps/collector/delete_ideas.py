import os, urllib.request

url = os.environ['SUPABASE_URL'] + '/rest/v1/macro_ideas?id=not.is.null'
req = urllib.request.Request(url, headers={
    'apikey': os.environ['SUPABASE_SERVICE_KEY'],
    'Authorization': 'Bearer ' + os.environ['SUPABASE_SERVICE_KEY'],
    'Prefer': 'return=minimal'
}, method='DELETE')

try:
    with urllib.request.urlopen(req) as response:
        print("Deleted all records. HTTP", response.getcode())
except Exception as e:
    print("Error deleting:", e)
