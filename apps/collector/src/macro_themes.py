"""자율 테마 발굴·랭킹 엔진 (v10).

macro_news/news(서사) + prices_daily(가격) + financials_q(실적)을 결합해
9개 고정 테마를 객관 스코어로 랭킹한다.

품질 개선 이력 (10회 반복 튜닝):
- v1→v2: QP 밀도→절대값, breadth 기준 강화(52w+3M)
- v3→v6: 중복제거·최신성·실적·빅테크·롤오버 추가
- v7: breadth 가중 최대화(0.38), evidence에 breadth 게이팅
- v8: 윈도우 5/7/14d 견고성 검증 통과
- v9(현재): QP 감성 방향(부정 신호 차감), 모멘텀 중앙값으로 폭등주 왜곡 보정,
           순환매 국면(1M 가속) 가점
- v10: macro_theme_ranks DB 영속화, 일간 변화 감지, 텔레그램 알람

실행 (일간 스케줄): python -m src.macro_themes [--dry-run]
임포트: from src.macro_themes import rank_themes, run_daily
"""
from __future__ import annotations
import datetime
import logging
import os
import sys
from collections import defaultdict

from .upsert import get_client, retry_execute
from .utils import telegram as tg

logger = logging.getLogger(__name__)

# ── 튜닝 상수 ─────────────────────────────────────────────────────────────────
WEIGHTS = {
    "evidence": 0.07,  # 기사 서사량 (breadth 게이팅 적용)
    "qp_net":   0.09,  # 순 Q/P 방향성 (긍정-부정×1.5, v9)
    "tech":     0.32,  # 바스켓 상위 3개 평균 모멘텀 (v11: median 롤백 — breadth가 다양성 담당)
    "breadth":  0.38,  # 신고가권+3M양 종목 수 (핵심 신호)
    "fund":     0.07,  # 영업이익 YoY 가속
    "bigtech":  0.06,  # 빅테크발언 선행 가점
    "accel":    0.01,  # 순환매 초기 보너스 (소가중 — 기존 테마 페널티 방지)
}
RISK_PENALTY   = 12   # 바스켓 60%+ 1M 음수 시 감점
ALERT_RANK_UP  = 2    # 이 이상 순위 상승 시 텔레그램 알람
ALERT_NEW_ALGN = True # 신규 정렬 종목 진입 시 알람

# ── 테마 택소노미 ──────────────────────────────────────────────────────────────
THEMES: dict[str, dict] = {
    "AI반도체/HBM":     {
        "kw": ["반도체", "hbm", "ai 메모리", "엔비디아", "nvidia", "gpu", "파운드리", "d램", "닷컴"],
        "basket": ["000660", "005930", "042700", "000990", "058470"],
    },
    "전자부품/AI기판": {
        "kw": ["mlcc", "기판", "fc-bga", "pcb", "적층세라믹", "패키징", "fc bga"],
        "basket": ["009150", "011070", "090460", "029460"],
    },
    "내수소비/유통/명품": {
        "kw": ["백화점", "명품", "유통", "관광", "면세", "뷰티", "화장품", "외식", "한류", "외국인 소비", "지갑"],
        "basket": ["004170", "023530", "069960", "008770", "031430", "007310", "278470", "139480"],
    },
    "조선/방산": {
        "kw": ["조선", "방산", "선박", "lng운반", "엔진", "함정", "잠수함", "해양플랜트"],
        "basket": ["329180", "010140", "042660", "012450", "064350"],
    },
    "바이오/제약": {
        "kw": ["바이오", "제약", "임상", "fda", "신약", "치료제", "항체", "지방간염", "비만약"],
        "basket": ["006280", "069620", "347850", "007390", "068270"],
    },
    "2차전지/ESS": {
        "kw": ["2차전지", "배터리", "ess", "양극재", "리튬", "캐즘 극복", "전기차"],
        "basket": ["373220", "051910", "006400", "247540"],
    },
    "금융/밸류업": {
        "kw": ["밸류업", "배당", "은행", "증권", "보험", "금융지주", "저pbr", "자사주"],
        "basket": ["032830", "005940", "105560", "138040"],
    },
    "로봇/피지컬AI": {
        "kw": ["로봇", "피지컬ai", "피지컬 ai", "휴머노이드", "자율주행"],
        "basket": ["307950", "012330", "108490", "056080"],
    },
    "원전/전력": {
        "kw": ["원전", "전력", "송전", "변압기", "전기기기", "송배전", "퓨얼셀", "소형원전"],
        "basket": ["052690", "051600", "015760", "336260"],
    },
}

# v9: QP 긍정 신호 (가산) vs 부정 신호 (차감) 분리
QP_POS = [
    "실적", "영업이익 증가", "어닝", "수주", "매출 증가", "급증", "역대", "신고가",
    "수요 증가", "단가 인상", "호황", "흑자", "최대", "상향", "돌파", "폭증", "수혜",
    "사상 최", "목표가 상향", "목표주가 상향",
]
QP_NEG = [
    "영업이익 감소", "적자", "하향", "목표가 하향", "목표주가 하향", "매출 감소",
    "수요 감소", "단가 하락", "부진", "실망", "경고", "위기", "하락",
]


def _kw_hit(text: str, kws: list[str]) -> bool:
    return any(k.lower() in text for k in kws)


def _median(vals: list[float]) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    n = len(s)
    return (s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2)


# ── 핵심 랭킹 함수 ─────────────────────────────────────────────────────────────
def rank_themes(window_days: int = 14) -> list[dict]:
    client = get_client()

    latest_res = retry_execute(
        lambda: client.table("macro_news").select("published_at")
        .order("published_at", desc=True).limit(1).execute()
    )
    latest = datetime.date.fromisoformat(
        (latest_res.data or [{}])[0].get("published_at", "2026-01-01")[:10]
    )
    since = (latest - datetime.timedelta(days=window_days)).isoformat()

    macro = retry_execute(
        lambda: client.table("macro_news")
        .select("title,summary,category,published_at")
        .gte("published_at", f"{since}T00:00:00Z")
        .order("published_at", desc=True).limit(400).execute()
    ).data or []

    news = retry_execute(
        lambda: client.table("news")
        .select("title,summary,published_at").eq("lang", "ko")
        .gte("published_at", f"{since}T00:00:00Z")
        .order("published_at", desc=True).limit(600).execute()
    ).data or []

    # 기사 풀: 제목 중복 제거 + 최신성 가중
    seen: set[str] = set()
    pool: list[tuple[str, float, bool]] = []
    for src, is_macro in ((macro, True), (news, False)):
        for a in src:
            title = a.get("title", "")
            if not title or title in seen:
                continue
            seen.add(title)
            txt = (title + " " + (a.get("summary") or "")).lower()
            d = a.get("published_at", "")[:10]
            age = (latest - datetime.date.fromisoformat(d)).days if d else window_days
            if age > window_days:
                continue
            w = 1.0 if age <= 3 else (0.7 if age <= 7 else 0.45)
            pool.append((txt, w, is_macro and a.get("category") == "빅테크발언"))

    match_map = {
        m["ticker"]: m["category"]
        for m in (retry_execute(
            lambda: client.table("hundredx_category_matches")
            .select("ticker,category").is_("exited_at", "null").execute()
        ).data or [])
    }

    # psycopg2 bulk 조회 (REST 1000행 한도 우회)
    all_tickers = list({t for d in THEMES.values() for t in d["basket"]})
    price_map: dict[str, list[float]] = defaultdict(list)
    fund_by:   dict[str, list[dict]]  = defaultdict(list)
    db_url = os.environ.get("SUPABASE_DB_URL", "")

    if db_url:
        try:
            import psycopg2
            conn = psycopg2.connect(db_url)
            cur = conn.cursor()
            cur.execute(
                "SELECT ticker, close FROM prices_daily"
                " WHERE ticker = ANY(%s) ORDER BY ticker, date DESC",
                (all_tickers,),
            )
            for row in cur.fetchall():
                price_map[row[0]].append(float(row[1]))
            cur.execute(
                "SELECT ticker, fq, op_income FROM financials_q"
                " WHERE ticker = ANY(%s) AND fq ~ 'Q[1-4]$' AND op_income IS NOT NULL"
                " ORDER BY ticker, fq DESC",
                (all_tickers,),
            )
            for row in cur.fetchall():
                fund_by[row[0]].append({"fq": row[1], "op_income": float(row[2])})
            conn.close()
            logger.info("psycopg2 bulk fetch done: %d tickers", len(all_tickers))
        except Exception as e:
            logger.warning("psycopg2 failed: %s — REST fallback", e)

    if not price_map:
        for t in all_tickers:
            res = retry_execute(
                lambda: client.table("prices_daily").select("close")
                .eq("ticker", t).order("date", desc=True).limit(260).execute()
            )
            for r in (res.data or []):
                price_map[t].append(float(r["close"]))

    def _mom(t: str) -> dict | None:
        c = price_map.get(t, [])
        if not c or len(c) < 25:
            return None
        n52 = c[0] / max(c) * 100
        r1 = (c[0] / c[20] - 1) * 100 if len(c) > 20 else 0.0
        r3 = (c[0] / c[60] - 1) * 100 if len(c) > 60 else 0.0
        # v9: 6→1개월 단기 가속도 (순환매 초기 감지)
        r1_prev = (c[20] / c[40] - 1) * 100 if len(c) > 40 else 0.0
        accel = r1 - r1_prev  # 양수 = 최근 1M이 이전 1M보다 강함
        mom = n52 / 2 + max(0, min(25, r1)) + max(0, min(25, r3 / 2))
        return {
            "n52": round(n52, 1), "r1": round(r1, 1), "r3": round(r3, 1),
            "mom": round(mom, 1), "accel": round(accel, 1),
        }

    def _fund(t: str) -> float | None:
        q = fund_by.get(t, [])
        if len(q) < 5:
            return None
        cur_v, yoy = q[0]["op_income"], q[4]["op_income"]
        if yoy and yoy > 0:
            return max(0.0, min(1.0, 0.5 + (cur_v / yoy - 1)))
        return None

    mom_cache  = {t: _mom(t)  for t in all_tickers}
    fund_cache = {t: _fund(t) for t in all_tickers}

    name_map = {
        s["ticker"]: s["name_kr"] for s in (retry_execute(
            lambda: client.table("stocks").select("ticker,name_kr")
            .in_("ticker", all_tickers).execute()
        ).data or [])
    }

    rows: list[dict] = []
    for name, d in THEMES.items():
        th = [(t, w, bt) for (t, w, bt) in pool if _kw_hit(t, d["kw"])]
        wvol = sum(w for _, w, _ in th)

        # v9: 순 QP = 긍정 가산 - 부정 차감
        qp_pos = sum(w for t, w, _ in th if _kw_hit(t, QP_POS))
        qp_neg = sum(w for t, w, _ in th if _kw_hit(t, QP_NEG))
        qp_net = max(0.0, qp_pos - qp_neg * 1.5)  # 부정은 1.5배 가중 차감

        bigtech = any(bt for _, _, bt in th)
        evidence_raw = min(1.0, wvol / 12)

        bm = [mom_cache[t] for t in d["basket"] if mom_cache.get(t)]
        mom_vals = [m["mom"] for m in bm]

        # v11: 상위 3개 평균 (breadth 축이 다양성 담당, tech는 선도주 강도만 반영)
        top_vals = sorted(mom_vals, reverse=True)[:3]
        tech_med = (sum(top_vals) / len(top_vals) / 100) if top_vals else 0

        aligned = sum(1 for m in bm if m["n52"] >= 85 and m["r3"] > 0)
        breadth  = min(1.0, aligned / 3)
        evidence = evidence_raw * (0.5 + 0.5 * breadth)  # 기사홍수 게이팅
        qp_s     = min(1.0, qp_net / 5)

        funds = [fund_cache[t] for t in d["basket"] if fund_cache.get(t) is not None]
        fund  = sum(funds) / len(funds) if funds else 0.5

        # v9: 순환매 초기 가점 (바스켓 50%+ 가속 양수)
        accel_cnt = sum(1 for m in bm if m.get("accel", 0) > 0)
        accel_s = min(1.0, accel_cnt / max(1, len(bm) / 2))

        rollover = sum(1 for m in bm if m["r1"] < 0)
        score = 100 * (
            WEIGHTS["evidence"] * evidence
            + WEIGHTS["qp_net"]  * qp_s
            + WEIGHTS["tech"]    * tech_med
            + WEIGHTS["breadth"] * breadth
            + WEIGHTS["fund"]    * fund
            + WEIGHTS["bigtech"] * (1.0 if bigtech else 0.0)
            + WEIGHTS["accel"]   * accel_s
        )
        if bm and rollover >= len(bm) * 0.6:
            score -= RISK_PENALTY

        cand = sorted(
            [{"ticker": t, "name": name_map.get(t), "mom": mom_cache[t]} for t in d["basket"] if mom_cache.get(t)],
            key=lambda x: x["mom"]["mom"], reverse=True,
        )
        rows.append({
            "theme": name, "score": round(score, 1),
            "evidence_wvol": round(wvol, 1),
            "qp_pos": round(qp_pos, 1), "qp_neg": round(qp_neg, 1), "qp_net": round(qp_net, 1),
            "tech": round(tech_med * 100, 1), "aligned": aligned,
            "fund": round(fund, 2), "bigtech": bigtech, "accel": round(accel_s, 2),
            "candidates": [{
                "ticker": c["ticker"], "name": c["name"],
                **c["mom"], "hundredx_match": match_map.get(c["ticker"]),
            } for c in cand],
        })

    rows.sort(key=lambda x: x["score"], reverse=True)
    return rows


# ── 일간 실행: 저장 + 변화 감지 + 텔레그램 ───────────────────────────────────
def run_daily(dry_run: bool = False) -> None:
    rows = rank_themes()
    client = get_client()

    # 오늘 날짜 (latest published_at 기준)
    latest_res = retry_execute(
        lambda: client.table("macro_news").select("published_at")
        .order("published_at", desc=True).limit(1).execute()
    )
    today_str = (latest_res.data or [{}])[0].get("published_at", "2026-01-01")[:10]
    today = datetime.date.fromisoformat(today_str)
    yesterday = (today - datetime.timedelta(days=1)).isoformat()

    # 어제 랭킹 조회
    prev_res = retry_execute(
        lambda: client.table("macro_theme_ranks")
        .select("theme,rank,aligned,candidates")
        .eq("run_date", yesterday).execute()
    )
    prev_map = {r["theme"]: r for r in (prev_res.data or [])}

    alerts: list[str] = []
    upsert_rows = []

    for rank, r in enumerate(rows, 1):
        theme = r["theme"]
        prev = prev_map.get(theme)

        # 어제 대비 순위 변화
        rank_up = 0
        if prev:
            rank_up = prev["rank"] - rank  # 양수 = 상승

        # 신규 정렬 종목 감지 (어제 aligned 집합 → 오늘 aligned 집합)
        today_aligned = {c["ticker"] for c in r["candidates"] if c.get("n52", 0) >= 85 and c.get("r3", 0) > 0}
        prev_aligned: set[str] = set()
        if prev and prev.get("candidates"):
            prev_aligned = {c["ticker"] for c in prev["candidates"] if c.get("n52", 0) >= 85 and c.get("r3", 0) > 0}
        new_aligned = today_aligned - prev_aligned

        # 알람 조건 — prev 데이터가 있을 때만 (첫 실행 false alarm 방지)
        if prev and rank_up >= ALERT_RANK_UP and r["score"] >= 50:
            alerts.append(
                f"📈 <b>{theme}</b> 테마 순위 상승\n"
                f"   {prev['rank']}위 → <b>{rank}위</b>  (점수 {r['score']})\n"
                f"   정렬 종목 {r['aligned']}개 | 신규 진입: {len(new_aligned)}개"
            )
        if prev and ALERT_NEW_ALGN and new_aligned and r["score"] >= 50:
            tickers_str = ", ".join(sorted(new_aligned)[:5])
            alerts.append(
                f"⭐ <b>{theme}</b> 신규 종목 신고가 정렬 진입\n"
                f"   [{tickers_str}]\n"
                f"   테마 점수 {r['score']} | 현재 {rank}위"
            )

        upsert_rows.append({
            "run_date": today_str,
            "theme": theme,
            "rank": rank,
            "score": r["score"],
            "aligned": r["aligned"],
            "candidates": r["candidates"],
        })

    if not dry_run:
        # DB 저장
        retry_execute(
            lambda: client.table("macro_theme_ranks")
            .upsert(upsert_rows, on_conflict="run_date,theme").execute()
        )
        logger.info("macro_theme_ranks upserted %d rows for %s", len(upsert_rows), today_str)

        # 텔레그램 알람
        if alerts:
            header = f"🔔 <b>매크로 테마 변화 감지</b> ({today_str})\n"
            tg.send_message(header + "\n\n".join(alerts))
            logger.info("Telegram alert sent: %d events", len(alerts))
        else:
            logger.info("No alert conditions triggered.")
    else:
        logger.info("[dry-run] would upsert %d rows, %d alerts", len(upsert_rows), len(alerts))

    # 콘솔 출력
    print(f"\n{'점수':>6} {'테마':<18} {'순위':>4} {'정렬':>4} {'QP+':>5} {'QP-':>5} {'가속':>5}")
    for rank, r in enumerate(rows, 1):
        prev = prev_map.get(r["theme"])
        delta = f"(+{prev['rank']-rank})" if prev and prev['rank'] != rank else ""
        print(f"{r['score']:>6} {r['theme']:<18} {rank:>3}{delta:<5} {r['aligned']:>4} {r['qp_pos']:>5} {r['qp_neg']:>5} {r['accel']:>5}")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    dry_run = "--dry-run" in sys.argv
    run_daily(dry_run=dry_run)


if __name__ == "__main__":
    main()
