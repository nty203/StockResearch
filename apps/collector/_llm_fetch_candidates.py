"""LLM 검증 후보 종목 + 공시 출력 (verify-stocks 스킬용).

Usage:
  python _llm_fetch_candidates.py [--days 3] [--category 임상_파이프라인] [--limit 20]

출력: JSON (stdout)
  {
    "candidates": [
      {
        "match_id": "uuid",
        "ticker": "082740",
        "name": "한화엔진",
        "sector": "조선/엔진",
        "category": "임상_파이프라인",
        "confidence": 0.75,
        "detected_at": "2026-05-23T...",
        "filings": [
          {
            "id": "uuid",
            "headline": "...",
            "body": "...",  # raw_text 앞 500자
            "filed_at": "2026-05-20"
          }
        ],
        "evidence_keywords": ["CE 인증", "안전성"]
      }
    ],
    "total": 12,
    "fetched_at": "2026-05-23T..."
  }
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
if sys.stdout.encoding != "utf-8":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from dotenv import load_dotenv
load_dotenv()
from supabase import create_client

client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=3, help="최근 N일 이내 탐지된 것만")
    parser.add_argument("--category", type=str, default=None, help="특정 카테고리만")
    parser.add_argument("--limit", type=int, default=20, help="최대 처리 건수")
    parser.add_argument("--ticker", type=str, default=None, help="특정 티커만")
    args = parser.parse_args()

    cutoff = (datetime.now(timezone.utc) - timedelta(days=args.days)).isoformat()

    # 후보 조회
    q = (
        client.table("hundredx_category_matches")
        .select("id, ticker, category, confidence, evidence, first_detected_at")
        .is_("exited_at", "null")
        .gte("first_detected_at", cutoff)
        .order("first_detected_at", desc=True)
        .limit(args.limit)
    )
    if args.category:
        q = q.eq("category", args.category)
    if args.ticker:
        q = q.eq("ticker", args.ticker)

    matches = q.execute().data or []

    candidates = []
    for m in matches:
        ticker = m["ticker"]

        # 종목 정보
        stk = client.table("stocks").select("name_kr, sector_tag").eq("ticker", ticker).execute()
        name = stk.data[0].get("name_kr", ticker) if stk.data else ticker
        sector = stk.data[0].get("sector_tag") or "" if stk.data else ""

        # 관련 공시 (최근 3건)
        filings_res = (
            client.table("filings")
            .select("id, headline, raw_text, filed_at")
            .eq("ticker", ticker)
            .order("filed_at", desc=True)
            .limit(3)
            .execute()
        )
        filings = []
        for f in (filings_res.data or []):
            body = (f.get("raw_text") or "")[:600].strip()
            filings.append({
                "id": str(f.get("id", "")),
                "headline": (f.get("headline") or "")[:200],
                "body": body,
                "filed_at": str(f.get("filed_at", ""))[:10],
            })

        # evidence에서 키워드 추출
        ev_list = m.get("evidence") or []
        kw_hits = []
        for ev in ev_list:
            if ev.get("source_type") == "keywords":
                excerpt = ev.get("text_excerpt", "")
                # "공급 병목: k1, k2 | 섹터:..." 형식에서 키워드만 추출
                if ": " in excerpt:
                    kw_part = excerpt.split("|")[0].split(": ", 1)[-1]
                    kw_hits.extend([k.strip() for k in kw_part.split(",") if k.strip()])

        candidates.append({
            "match_id": str(m["id"]),
            "ticker": ticker,
            "name": name,
            "sector": sector,
            "category": m["category"],
            "confidence": round(m.get("confidence") or 0, 3),
            "detected_at": str(m.get("first_detected_at", ""))[:19],
            "filings": filings,
            "evidence_keywords": list(set(kw_hits))[:8],
        })

    result = {
        "candidates": candidates,
        "total": len(candidates),
        "fetched_at": datetime.now(timezone.utc).isoformat()[:19],
        "params": {"days": args.days, "category": args.category, "limit": args.limit},
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
