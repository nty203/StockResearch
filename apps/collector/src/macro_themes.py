"""자율 테마 발굴·랭킹 엔진.

macro_news/news(서사) + prices_daily(가격 확인) + financials_q(실적)를 결합해
고정 테마 택소노미를 객관 스코어로 랭킹한다. macro-idea 스킬이 '어느 테마가
지금 핫한가'를 사람 주관 없이 선택하도록 시드를 제공한다.

설계 원칙 (10회 반복 튜닝으로 도출):
- 가격(정렬 폭·기술)을 신뢰하고 기사량은 저가중 + breadth로 게이팅
  → '뉴스는 많지만 안 움직이는' 테마(예: 금융 routine 뉴스)의 거품 제거
- 정렬 폭(breadth) = 신고가권(52w>=85%)이면서 3M 양(+)인 종목 수
  → 섹터 전반 이동 = 고품질 순환매 신호 (백화점이 자율 부상하는 핵심 축)
- 빅테크 거물 발언은 선행 신호 가점

실행: python -m src.macro_themes        (랭킹 출력)
임포트: from src.macro_themes import rank_themes
"""
from __future__ import annotations
import datetime
import logging

from .upsert import get_client, retry_execute

logger = logging.getLogger(__name__)

WEIGHTS = {"evidence": 0.08, "qp": 0.07, "tech": 0.32, "breadth": 0.38, "fund": 0.08, "bigtech": 0.07}
RISK_PENALTY = 12  # 바스켓 60%+ 1M 음수(고점 피로) 시 감점

THEMES: dict[str, dict] = {
    "AI반도체/HBM":     {"kw": ["반도체", "hbm", "ai 메모리", "엔비디아", "gpu", "파운드리", "d램", "닷컴"], "basket": ["000660", "005930", "042700", "000990", "058470"]},
    "전자부품/AI기판":   {"kw": ["mlcc", "기판", "fc-bga", "pcb", "적층", "콘덴서", "패키징"], "basket": ["009150", "011070", "090460", "029460"]},
    "내수소비/유통/명품": {"kw": ["백화점", "명품", "유통", "소비", "관광", "면세", "뷰티", "화장품", "외식", "한류", "지갑"], "basket": ["004170", "023530", "069960", "008770", "031430", "007310", "278470", "139480"]},
    "조선/방산":        {"kw": ["조선", "방산", "선박", "lng", "엔진", "함정", "잠수함", "해양"], "basket": ["329180", "010140", "042660", "012450", "064350"]},
    "바이오/제약":      {"kw": ["바이오", "제약", "임상", "fda", "신약", "치료제", "항체"], "basket": ["006280", "069620", "347850", "007390", "068270"]},
    "2차전지/ESS":     {"kw": ["2차전지", "배터리", "ess", "양극재", "리튬", "캐즘"], "basket": ["373220", "051910", "006400", "247540"]},
    "금융/밸류업":      {"kw": ["밸류업", "배당", "은행", "증권", "보험", "금융지주", "저pbr"], "basket": ["032830", "005940", "105560", "138040"]},
    "로봇/피지컬AI":    {"kw": ["로봇", "피지컬", "휴머노이드", "자율주행"], "basket": ["307950", "012330", "108490", "056080"]},
    "원전/전력":       {"kw": ["원전", "전력", "송전", "변압기", "전기기기", "송배전", "퓨얼셀"], "basket": ["052690", "051600", "015760", "336260"]},
}
QP = ["실적", "영업이익", "어닝", "수주", "매출", "급증", "역대", "신고가", "수요", "단가", "호황", "흑자", "증가", "최대", "상향", "돌파", "폭증", "수혜", "사상 최", "목표가"]


def _kw_hit(text: str, kws: list[str]) -> bool:
    return any(k.lower() in text for k in kws)



def rank_themes(window_days: int = 14) -> list[dict]:
    client = get_client()
    # 최신 published_at 기준 윈도우 (Date.now 비의존)
    latest_res = retry_execute(lambda: client.table("macro_news").select("published_at").order("published_at", desc=True).limit(1).execute())
    latest = datetime.date.fromisoformat((latest_res.data or [{}])[0].get("published_at", "2026-01-01")[:10])
    since = (latest - datetime.timedelta(days=window_days)).isoformat()

    macro = retry_execute(lambda: client.table("macro_news").select("title,summary,category,published_at").gte("published_at", f"{since}T00:00:00Z").order("published_at", desc=True).limit(400).execute()).data or []
    news = retry_execute(lambda: client.table("news").select("title,summary,published_at").eq("lang", "ko").gte("published_at", f"{since}T00:00:00Z").order("published_at", desc=True).limit(600).execute()).data or []

    # 기사 풀: 제목 중복 제거 + 최신성 가중
    seen, pool = set(), []
    for src, is_macro in ((macro, True), (news, False)):
        for a in src:
            title = a.get("title", "")
            if not title or title in seen:
                continue
            seen.add(title)
            txt = (title + " " + (a.get("summary") or "")).lower()
            d = a.get("published_at", "")[:10]
            age = (latest - datetime.date.fromisoformat(d)).days if d else window_days
            w = 1.0 if age <= 3 else (0.7 if age <= 7 else 0.45)
            pool.append((txt, w, is_macro and a.get("category") == "빅테크발언"))

    match_map = {m["ticker"]: m["category"] for m in (retry_execute(lambda: client.table("hundredx_category_matches").select("ticker,category").is_("exited_at", "null").execute()).data or [])}

    # 전체 바스켓 티커를 psycopg2로 bulk 조회 (REST limit 회피, 쿼리 수 ~40 → 2)
    import os
    from collections import defaultdict
    all_tickers = list({t for d in THEMES.values() for t in d["basket"]})
    logger.info("Bulk-fetching prices/financials for %d tickers via psycopg2…", len(all_tickers))

    price_map: dict[str, list[float]] = defaultdict(list)
    fund_by: dict[str, list] = defaultdict(list)
    db_url = os.environ.get("SUPABASE_DB_URL", "")
    if db_url:
        try:
            import psycopg2
            conn = psycopg2.connect(db_url)
            cur = conn.cursor()
            cur.execute(
                "SELECT ticker, close FROM prices_daily WHERE ticker = ANY(%s) ORDER BY ticker, date DESC",
                (all_tickers,)
            )
            for row in cur.fetchall():
                price_map[row[0]].append(float(row[1]))  # Decimal → float
            cur.execute(
                "SELECT ticker, fq, op_income FROM financials_q WHERE ticker = ANY(%s) AND fq ~ 'Q[1-4]$' AND op_income IS NOT NULL ORDER BY ticker, fq DESC",
                (all_tickers,)
            )
            for row in cur.fetchall():
                fund_by[row[0]].append({"fq": row[1], "op_income": float(row[2])})
            conn.close()
        except Exception as e:
            logger.warning("psycopg2 bulk fetch failed: %s — falling back to REST", e)
    if not price_map:
        # REST 폴백: ticker당 개별 쿼리 (느리지만 안전)
        for t in all_tickers:
            res = retry_execute(lambda: client.table("prices_daily").select("close").eq("ticker", t).order("date", desc=True).limit(260).execute())
            for r in (res.data or []):
                price_map[t].append(r["close"])

    def _mom_from_cache(t: str) -> dict | None:
        c = price_map.get(t, [])
        if not c or len(c) < 25:
            return None
        n52 = c[0] / max(c) * 100
        r1 = (c[0] / c[20] - 1) * 100 if len(c) > 20 else 0.0
        r3 = (c[0] / c[60] - 1) * 100 if len(c) > 60 else 0.0
        mom = n52 / 2 + max(0, min(25, r1)) + max(0, min(25, r3 / 2))
        return {"n52": round(n52, 1), "r1": round(r1, 1), "r3": round(r3, 1), "mom": round(mom, 1)}

    def _fund_from_cache(t: str) -> float | None:
        q = fund_by.get(t, [])
        if len(q) < 5:
            return None
        cur_v, yoy = q[0]["op_income"], q[4]["op_income"]
        if yoy and yoy > 0:
            return max(0.0, min(1.0, 0.5 + (cur_v / yoy - 1)))
        return None

    mom_cache: dict[str, dict | None] = {t: _mom_from_cache(t) for t in all_tickers}
    fund_cache: dict[str, float | None] = {t: _fund_from_cache(t) for t in all_tickers}

    rows = []
    for name, d in THEMES.items():
        th = [(t, w, bt) for (t, w, bt) in pool if _kw_hit(t, d["kw"])]
        wvol = sum(w for _, w, _ in th)
        qp = sum(w for t, w, _ in th if _kw_hit(t, QP))
        bigtech = any(bt for _, _, bt in th)
        evidence_raw = min(1.0, wvol / 12)
        qp_s = min(1.0, qp / 5)
        bm = [mom_cache[t] for t in d["basket"] if mom_cache.get(t)]
        top = sorted([m["mom"] for m in bm], reverse=True)[:5]
        tech = (sum(top) / len(top)) / 100 if top else 0
        aligned = sum(1 for m in bm if m["n52"] >= 85 and m["r3"] > 0)
        breadth = min(1.0, aligned / 3)
        evidence = evidence_raw * (0.5 + 0.5 * breadth)  # 가격 미확인 기사홍수 게이팅
        funds = [fund_cache[t] for t in d["basket"] if fund_cache.get(t) is not None]
        fund = sum(funds) / len(funds) if funds else 0.5
        rollover = sum(1 for m in bm if m["r1"] < 0)
        score = 100 * (WEIGHTS["evidence"] * evidence + WEIGHTS["qp"] * qp_s + WEIGHTS["tech"] * tech
                       + WEIGHTS["breadth"] * breadth + WEIGHTS["fund"] * fund + WEIGHTS["bigtech"] * (1 if bigtech else 0))
        if bm and rollover >= len(bm) * 0.6:
            score -= RISK_PENALTY
        # 바스켓 후보 (모멘텀 순)
        cand = sorted(
            [{"ticker": t, "mom": mom_cache[t]} for t in d["basket"] if mom_cache.get(t)],
            key=lambda x: x["mom"]["mom"], reverse=True,
        )
        rows.append({
            "theme": name, "score": round(score, 1),
            "evidence_wvol": round(wvol, 1), "qp": round(qp, 1),
            "tech": round(tech * 100, 1), "aligned": aligned, "fund": round(fund, 2),
            "bigtech": bigtech,
            "candidates": [{"ticker": c["ticker"], **c["mom"], "hundredx_match": match_map.get(c["ticker"])} for c in cand],
        })
    rows.sort(key=lambda x: x["score"], reverse=True)
    return rows


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    rows = rank_themes()
    print(f"{'score':>6} {'theme':<18} {'artW':>6} {'QP':>5} {'tech':>5} {'algn':>4} {'fund':>5} {'BT':>3}")
    for r in rows:
        print(f"{r['score']:>6} {r['theme']:<18} {r['evidence_wvol']:>6} {r['qp']:>5} {r['tech']:>5} {r['aligned']:>4} {r['fund']:>5} {'BT' if r['bigtech'] else '':>3}")


if __name__ == "__main__":
    main()
