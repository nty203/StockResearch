import urllib.request
import json

url = "https://yngcjwkjppqclbuwqzkm.supabase.co/rest/v1/macro_ideas?id=eq.94e35beb-98cb-4a9a-8959-3a50633fa812&select=*"
headers = {
    "apikey": "***REMOVED***",
    "Authorization": "Bearer ***REMOVED***"
}

req = urllib.request.Request(url, headers=headers)
with urllib.request.urlopen(req) as response:
    data = response.read().decode('utf-8')
    with open('macro_output.json', 'w', encoding='utf-8') as f:
        f.write(data)
