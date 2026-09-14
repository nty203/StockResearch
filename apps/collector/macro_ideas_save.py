"""macro_ideas_save.py — 범용 macro_ideas 저장 유틸리티.

에이전트가 생성한 투자 가설 JSON 배열을 stdin으로 받아 Supabase에 저장한다.
고정 아이디어 배열 없음 — 호출자(에이전트)가 완전히 제어한다.

사용법:
    echo '[{...}]' | uv run python macro_ideas_save.py
    또는:
    cat ideas.json | uv run python macro_ideas_save.py
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

sys.stdout.reconfigure(encoding="utf-8")


def _load_env():
    for path in [".env", "apps/collector/.env"]:
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k and k not in os.environ:
                        os.environ[k] = v


_load_env()

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: SUPABASE_URL / SUPABASE_SERVICE_KEY not set", file=sys.stderr)
    sys.exit(1)

BASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

KST = timezone(timedelta(hours=9))


def _req(method, url, body=None):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers=BASE_HEADERS, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read().decode("utf-8")
            return r.getcode(), (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        return e.code, raw


def save_ideas(ideas):
    if not ideas:
        print("No ideas to save.")
        return

    today_str = datetime.now(KST).strftime("%Y-%m-%d")
    now_str = datetime.now(timezone.utc).isoformat()

    for idea in ideas:
        idea.setdefault("date", today_str)
        idea.setdefault("created_at", now_str)
        idea.setdefault("raw_json", {})

    themes_to_delete = list({idea["theme"] for idea in ideas})
    print(f"Deleting existing records (date={today_str}, {len(themes_to_delete)} themes)...")
    for theme in themes_to_delete:
        encoded = urllib.parse.quote(theme)
        url = f"{SUPABASE_URL}/rest/v1/macro_ideas?date=eq.{today_str}&theme=eq.{encoded}"
        code, _ = _req("DELETE", url)
        print(f"  [{theme}] delete status={code}")

    url = f"{SUPABASE_URL}/rest/v1/macro_ideas"
    code, result = _req("POST", url, ideas)

    if code == 201:
        saved = result if isinstance(result, list) else []
        print(f"\nSaved {len(saved)} ideas (HTTP {code})")
    else:
        print(f"\nSave failed (HTTP {code}): {result}")
        sys.exit(1)

    print("\n" + "=" * 70)
    print(f"[{today_str}] macro-idea complete - {len(ideas)} hypotheses saved")
    print("=" * 70)
    for i, idea in enumerate(ideas, 1):
        cands = idea.get("candidates", [])
        top2 = " / ".join(
            f"{c['name']}({c['ticker']}) {c.get('signal_flag', '')}"
            for c in cands[:2]
        )
        print(
            f"\n{i:>2}. [{idea['theme']}] {idea['title'][:60]}"
            f"\n    Score={idea.get('total_score')} | {idea.get('play_mode')}"
            f"\n    Top2: {top2 or '(none)'}"
        )
    print("\n-> Check /macro-ideas on the web dashboard")


if __name__ == "__main__":
    raw = sys.stdin.buffer.read().decode("utf-8").strip()
    if not raw:
        print("Error: No JSON data from stdin", file=sys.stderr)
        sys.exit(1)
    try:
        ideas = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"Error: JSON parse error: {e}", file=sys.stderr)
        sys.exit(1)
    if not isinstance(ideas, list):
        ideas = [ideas]
    save_ideas(ideas)
