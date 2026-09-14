import sys
import json
import re

sys.stdout.reconfigure(encoding='utf-8')

with open("scratch_fetched_news.json", "r", encoding="utf-8") as f:
    data = json.load(f)

macro_news = data.get("macro_news", [])

# Let's filter out routine earnings call presentations, securities fraud lawsuit announcements, real estate deals, etc.
noise_patterns = [
    r"Earnings Call Presentation", r"Securities Fraud Lawsuit", r"Shareholder Notice",
    r"Go player", r"KataGo", r"치킨집", r"병무청", r"국세청", r"Chungho Nais"
]

meaningful_events = []
for m in macro_news:
    title = m.get("title") or ""
    summary = m.get("summary") or ""
    cat = m.get("category") or ""
    pub = m.get("published_at") or ""
    src = m.get("source") or ""
    full_text = f"{title} {summary}"

    is_noise = False
    for pat in noise_patterns:
        if re.search(pat, full_text, re.IGNORECASE):
            is_noise = True
            break
    if not is_noise:
        meaningful_events.append({
            "pub": pub,
            "cat": cat,
            "src": src,
            "title": title,
            "summary": summary
        })

print(f"Total Macro News: {len(macro_news)}, Meaningful Events: {len(meaningful_events)}")

with open("filtered_macro_events.txt", "w", encoding="utf-8") as f:
    for idx, ev in enumerate(meaningful_events, 1):
        f.write(f"[{idx:03d}] [{ev['pub']}] [{ev['cat']}] [{ev['src']}]\n")
        f.write(f"TITLE: {ev['title']}\n")
        if ev['summary']:
            f.write(f"SUMMARY: {ev['summary']}\n")
        f.write("-" * 80 + "\n")

print("Saved to filtered_macro_events.txt")
