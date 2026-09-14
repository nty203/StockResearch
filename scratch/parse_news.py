import json

with open('scratch/window_news.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
    
with open('scratch/window_news.txt', 'w', encoding='utf-8') as f:
    for item in data:
        cat = item.get('category') or '기타'
        f.write(f"[{cat}] {item['title']}\n")
