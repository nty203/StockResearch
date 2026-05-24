"""LLM 검증 후보 종목 + 공시 출력 (verify-stocks 스킬용).

Usage:
  python _llm_fetch_candidates.py [--days 3] [--category 임상_파이프라인] [--limit 20]
  python _llm_fetch_candidates.py --include-verified   # 이미 검증된 종목 포함

출력: JSON (stdout)
  {
    "candidates": [
      {
        "match_id": "uuid",
        "ticker": "082740",
        "name": "한화엔진",
        "sector": "조선/엔진",
        "category": "공급_병목",
        "confidence": 0.80,
        "detected_at": "2026-05-22T...",
        "already_verified": false,        # true면 llm_verdict evidence 이미 있음
        "llm_verdict": null,              # "confirm" | "reject" | "uncertain" | null
        "is_library_stock": false,        # true면 library에 등록된 종목
        "library_categories": [],         # library에 등록된 카테고리 목록
        "financials": {
          "op_margin": 12.3,             # 영업이익률 (%)
          "roe": 18.5,                   # ROE (%)
          "revenue_bn": 4200.0,          # 매출 (억원)
          "net_income_bn": 320.0         # 순이익 (억원)
        },
        "filings": [...],
        "evidence_keywords": ["TC본더", "HBM"]
      }
    ],
    "total": 12,
    "skipped_verified": 5,
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


def _get_llm_verdict_from_evidence(ev_list: list) -> str | None:
    """evidence 목록에서 llm_verdict 판정 추출."""
    for ev in (ev_list or []):
        if isinstance(ev, dict) and ev.get("source_type") == "llm_verdict":
            text = ev.get("text_excerpt", "")
            if "LLM confirm" in text:
                return "confirm"
            if "LLM reject" in text:
                return "reject"
            if "LLM uncertain" in text:
                return "uncertain"
    return None


def _fetch_financials(ticker: str) -> dict:
    """financials_q에서 최근 재무 수치 + 품질 지표(F-Score/accruals/GP-A) 계산."""
    try:
        res = (
            client.table("financials_q")
            .select(
                "fq, op_margin, roe, roic, revenue, net_income, op_income, "
                "gross_profit, cfo, total_assets, total_equity, total_liab, debt_ratio, shares_out"
            )
            .eq("ticker", ticker)
            .like("fq", "%Q%")
            .order("fq", desc=True)
            .limit(12)
            .execute()
        )
        if not res.data:
            return {}
        rows = res.data
        row = rows[0]
        rev = row.get("revenue")
        ni = row.get("net_income")
        out = {
            "op_margin": round(float(row["op_margin"]), 1) if row.get("op_margin") is not None else None,
            "roe": round(float(row["roe"]), 1) if row.get("roe") is not None else None,
            "roic": round(float(row["roic"]), 1) if row.get("roic") is not None else None,
            "revenue_bn": round(float(rev) / 1e8, 0) if rev else None,
            "net_income_bn": round(float(ni) / 1e8, 0) if ni else None,
            "debt_ratio": round(float(row["debt_ratio"]), 1) if row.get("debt_ratio") is not None else None,
        }
        # 품질 지표 (Piotroski/Sloan/Novy-Marx) — 검증 정밀도 향상용
        try:
            import sys, os
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
            from hundredx.quality_metrics import (
                compute_gp_to_assets, compute_accruals_ratio, compute_piotroski_f_score,
            )
            out["f_score"] = compute_piotroski_f_score(rows)
            gp = compute_gp_to_assets(rows)
            out["gp_to_assets"] = round(gp, 3) if gp is not None else None
            ac = compute_accruals_ratio(rows)
            out["accruals_ratio"] = round(ac, 3) if ac is not None else None
        except Exception:
            pass
        return out
    except Exception:
        pass
    return {}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=3, help="최근 N일 이내 탐지된 것만")
    parser.add_argument("--category", type=str, default=None, help="특정 카테고리만")
    parser.add_argument("--limit", type=int, default=20, help="최대 처리 건수")
    parser.add_argument("--ticker", type=str, default=None, help="특정 티커만")
    parser.add_argument("--include-verified", action="store_true",
                        help="이미 LLM 검증된 종목도 포함 (기본: 제외)")
    args = parser.parse_args()

    cutoff = (datetime.now(timezone.utc) - timedelta(days=args.days)).isoformat()

    # library 종목 목록 사전 조회 (is_library_stock 판별용)
    lib_res = client.table("hundredx_library_stocks").select("ticker, category").execute()
    lib_by_ticker: dict[str, list[str]] = {}
    for row in (lib_res.data or []):
        lib_by_ticker.setdefault(row["ticker"], []).append(row["category"])

    # 후보 조회 (verified 제외를 위해 evidence 포함)
    q = (
        client.table("hundredx_category_matches")
        .select(
            "id, ticker, category, confidence, evidence, first_detected_at, "
            "fingerprint_score, fingerprint_library_ticker, fingerprint_dims, "
            "convergent_signals"
        )
        .is_("exited_at", "null")
        .gte("first_detected_at", cutoff)
        .order("first_detected_at", desc=True)
        .limit(args.limit * 3)  # 검증된 종목 제외 후에도 충분하도록 여유 있게 조회
    )
    if args.category:
        q = q.eq("category", args.category)
    if args.ticker:
        q = q.eq("ticker", args.ticker)

    raw_matches = q.execute().data or []

    candidates = []
    skipped_verified = 0

    for m in raw_matches:
        if len(candidates) >= args.limit:
            break

        ticker = m["ticker"]
        ev_list = m.get("evidence") or []
        llm_verdict = _get_llm_verdict_from_evidence(ev_list)
        already_verified = llm_verdict is not None

        # 이미 검증된 종목은 --include-verified 없으면 스킵
        if already_verified and not args.include_verified:
            skipped_verified += 1
            continue

        # 종목 정보
        stk = client.table("stocks").select("name_kr, sector_tag").eq("ticker", ticker).execute()
        name = stk.data[0].get("name_kr") or ticker if stk.data else ticker
        sector = (stk.data[0].get("sector_tag") or "") if stk.data else ""

        # 재무 수치
        financials = _fetch_financials(ticker)

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
        kw_hits = []
        for ev in ev_list:
            if ev.get("source_type") == "keywords":
                excerpt = ev.get("text_excerpt", "")
                if ": " in excerpt:
                    kw_part = excerpt.split("|")[0].split(": ", 1)[-1]
                    kw_hits.extend([k.strip() for k in kw_part.split(",") if k.strip()])

        lib_cats = lib_by_ticker.get(ticker, [])
        # Fingerprint / convergent / quality 시그널 (LLM 판단 보조)
        fp_score = m.get("fingerprint_score")
        fp_lib = m.get("fingerprint_library_ticker")
        conv = m.get("convergent_signals") or []
        candidates.append({
            "match_id": str(m["id"]),
            "ticker": ticker,
            "name": name,
            "sector": sector,
            "category": m["category"],
            "confidence": round(m.get("confidence") or 0, 3),
            "detected_at": str(m.get("first_detected_at", ""))[:19],
            "already_verified": already_verified,
            "llm_verdict": llm_verdict,
            "is_library_stock": bool(lib_cats),
            "library_categories": lib_cats,
            "financials": financials,
            "filings": filings,
            "evidence_keywords": list(set(kw_hits))[:8],
            # Scanner가 함께 산출한 보조 시그널 — 검증 정밀도 향상용
            "fingerprint_score": round(fp_score, 2) if fp_score is not None else None,
            "fingerprint_library_ref": fp_lib,
            "convergent_signals": conv,  # ["insider_buy×2", "buyback×1"] 형태
        })

    result = {
        "candidates": candidates,
        "total": len(candidates),
        "skipped_verified": skipped_verified,
        "fetched_at": datetime.now(timezone.utc).isoformat()[:19],
        "params": {
            "days": args.days,
            "category": args.category,
            "limit": args.limit,
            "include_verified": args.include_verified,
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
