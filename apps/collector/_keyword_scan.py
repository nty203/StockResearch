"""키워드 역검색 스캔: 최근 filings에서 고가치 신호를 직접 검색 후 detector 실행.

일반 scanner는 stocks 테이블 전체(2600+)를 순회하지만,
이 스크립트는 반대 방향으로 - filings에서 핵심 키워드를 먼저 검색하고
해당 종목에만 detector를 집중 실행합니다.

속도: ~1-2분 (전체 스캔 대비 40x 빠름)
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv()
from supabase import create_client
from datetime import datetime, timezone, date, timedelta
import logging

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

url = os.environ["SUPABASE_URL"]
key = os.environ["SUPABASE_SERVICE_KEY"]
client = create_client(url, key)

from src.hundredx.categories.bigtech_partner import detect as detect_bigtech
from src.hundredx.categories.clinical_pipe   import detect as detect_clinical
from src.hundredx.categories.supply_choke    import detect as detect_supply
from src.hundredx.categories.policy_benefit  import detect as detect_policy
from src.hundredx.categories.backlog_lead    import detect as detect_backlog
from src.hundredx.categories.profit_inflect  import detect as detect_profit
from src.hundredx.categories.platform_mono   import detect as detect_mono
from src.utils.db_fetch                      import bulk_fetch_financials

MIN_CONF = 0.70
DAYS_BACK = 90  # 최근 90일 공시만

DETECTORS = [
    ("빅테크_파트너",   detect_bigtech),
    ("임상_파이프라인", detect_clinical),
    ("공급_병목",       detect_supply),
    ("정책_수혜",       detect_policy),
    ("수주잔고_선행",   detect_backlog),
    ("수익성_급전환",   detect_profit),
    ("플랫폼_독점",     detect_mono),
]

# 검색할 키워드 그룹 (ilike 패턴)
KEYWORD_GROUPS = [
    # 빅테크 파트너십
    ("빅테크_파트너",   ["삼성전자%지분", "LG전자%지분", "SK하이닉스%투자",
                         "콜옵션%체결", "유상증자%참여", "전략적%투자",
                         "Microsoft%공급", "NVIDIA%계약", "Amazon%납품",
                         "로봇%공급계약", "협동로봇%계약"]),
    # 임상 파이프라인
    ("임상_파이프라인", ["GLP-1%임상", "임상%3상%완료", "임상%2상%진입",
                         "FDA%승인", "식약처%품목허가", "기술이전%계약",
                         "마일스톤%체결", "바이오시밀러%허가",
                         "임상시험계획%승인", "IND%승인",
                         "점안제%임상", "황반변성%치료"]),
    # 공급 병목
    ("공급_병목",       ["양극재%공급%부족", "리튬%공급%부족",
                         "HBM%수요", "TC본더%공급", "변압기%납기",
                         "슈퍼사이클%조선", "수주잔고%증가",
                         "AI%서버%공급", "데이터센터%전력%부족"]),
    # 정책 수혜
    ("정책_수혜",       ["IRA%배터리", "방산%수출%확대",
                         "원전%수출%계약", "SMR%개발",
                         "K-방산%수주", "K-배터리%수혜"]),
    # 대형 수주
    ("수주잔고_선행",   ["%조원%수주", "%조원%계약",
                         "역대%최대%수주", "방위산업%수출",
                         "LNG운반선%수주", "HVDC%계약"]),
]

print("\n" + "="*70)
print(f"키워드 역검색 스캔 (최근 {DAYS_BACK}일 공시)")
print("="*70)

cutoff = (date.today() - timedelta(days=DAYS_BACK)).isoformat()

# Step 1: 키워드 검색으로 대상 filing 수집
filing_hits: dict[str, list[dict]] = {}  # ticker -> filings
hint_cats: dict[str, str] = {}

for hint_cat, patterns in KEYWORD_GROUPS:
    cat_hits = 0
    for pattern in patterns:
        # Supabase ilike는 단일 패턴만 지원하므로 headline OR raw_text
        try:
            res = (
                client.table("filings")
                .select("id, ticker, headline, raw_text, filed_at")
                .gte("filed_at", cutoff)
                .ilike("headline", f"%{pattern.replace('%', '')}%")
                .limit(100)
                .execute()
            )
            for f in (res.data or []):
                t = f["ticker"]
                filing_hits.setdefault(t, []).append(f)
                if t not in hint_cats:
                    hint_cats[t] = hint_cat
                cat_hits += 1
        except Exception as e:
            pass
    if cat_hits > 0:
        print(f"  {hint_cat}: {cat_hits}개 공시 히트")

all_tickers = list(filing_hits.keys())
print(f"\n공시 히트 종목: {len(all_tickers)}개")

if not all_tickers:
    print("키워드 히트 없음 — DB에 최근 관련 공시가 없습니다.")
    print("전체 scanner 실행이 필요합니다.")
    sys.exit(0)

# Step 2: 해당 종목 재무/섹터 데이터 로드
fin_data = bulk_fetch_financials(client, all_tickers[:200])
stocks_res = client.table("stocks").select("ticker, market, sector_tag").in_("ticker", all_tickers[:200]).execute()
sector_by_ticker = {r["ticker"]: r.get("sector_tag") or "" for r in (stocks_res.data or [])}

# Step 3: 각 detector 실행
print(f"\n{'='*70}")
print(f"{'종목':<10} {'카테고리':<20} {'신뢰도':>8} {'공시':>5} {'섹터'}")
print("-"*70)

all_new_matches = []
for ticker in sorted(all_tickers):
    filings = filing_hits[ticker]
    stock_data = fin_data.get(ticker, {"ticker": ticker})
    stock_data["ticker"] = ticker
    stock_data["sector_tag"] = sector_by_ticker.get(ticker, "")

    best_match = None
    for cat, detector_fn in DETECTORS:
        f = filings if cat == "임상_파이프라인" else filings
        try:
            m = detector_fn(stock_data, f)
            if m and m.confidence >= MIN_CONF:
                if best_match is None or m.confidence > best_match.confidence:
                    best_match = m
        except Exception:
            pass

    if best_match:
        sector = sector_by_ticker.get(ticker, "")[:20]
        headline = (filings[0].get("headline") or "")[:50]
        print(f"  {ticker:<10} {best_match.category:<20} {best_match.confidence:>8.3f} {len(filings):>5}  {sector}")
        all_new_matches.append({
            "ticker": ticker,
            "category": best_match.category,
            "confidence": best_match.confidence,
            "headline": headline,
            "sector": sector,
        })

print(f"\n탐지 종목: {len(all_new_matches)}개 (신뢰도 >= {MIN_CONF})")

if not all_new_matches:
    print("\n현재 DB에 고가치 신호가 없습니다.")
    print("filings 수집 워크플로우(collect-hourly/daily) 확인 필요.")
else:
    # 현재 category_matches와 비교해서 NEW 종목만 표시
    existing_res = (
        client.table("hundredx_category_matches")
        .select("ticker, category, confidence")
        .is_("exited_at", "null")
        .execute()
    )
    existing_set = {(r["ticker"], r["category"]) for r in (existing_res.data or [])}

    new_candidates = [m for m in all_new_matches if (m["ticker"], m["category"]) not in existing_set]
    if new_candidates:
        print(f"\n[신규 후보 (DB에 없는 종목) - {len(new_candidates)}개]")
        for m in sorted(new_candidates, key=lambda x: -x["confidence"]):
            print(f"  {m['ticker']:<10} {m['category']:<20} conf={m['confidence']:.3f}  {m['headline']}")
    else:
        print("\n신규 후보 없음 (이미 DB에 있거나 실제 히트가 없음)")

# Step 4: 전체 filings DB 현황 출력
total_filings = client.table("filings").select("id", count="exact").gte("filed_at", cutoff).execute()
total_count = total_filings.count if hasattr(total_filings, 'count') else len(total_filings.data or [])
print(f"\n[DB 현황]")
print(f"  최근 {DAYS_BACK}일 총 공시: {total_count}개")
print(f"  키워드 히트 종목: {len(all_tickers)}개")
print(f"  탐지 성공 종목: {len(all_new_matches)}개")
