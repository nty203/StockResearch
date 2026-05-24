"""미분류 라이브러리 종목 카테고리 할당 + PPTR 재생성.

분류 근거:
  000500 가온전선    → 전력_인프라    (AI 데이터센터 전력망 확충 수혜, 8개월 10.5x)
  000650 천일고속    → 단기_테마_급등  (버스/운수 테마, 37일 12.4x — 단기 급등)
  007810 코리아써키트 → 빅테크_파트너  (AI 서버용 고다층 MLB PCB, 1년 10.6x)
  017900 광전자      → 단기_테마_급등  (광반도체/LED 테마, 42일 10.1x)
  047040 대우건설    → 수주잔고_선행   (해외 EPC/중동 건설 대형 수주, 5.6개월 11.1x)
  049630 재영솔루텍  → 정책_수혜      (방산/EV 알루미늄 다이캐스팅, 4.5개월 10.0x)
  187660 페니트리움바이오 → 임상_파이프라인 (바이오 신약 개발, 8개월 16.4x)
  353200 대덕전자    → 빅테크_파트너  (AI 서버용 HDI/MLB 반도체 기판, 1년 10.5x)
  440110 파두        → 빅테크_파트너  (AI 데이터센터 SSD 컨트롤러 반도체, 1년 12.7x)
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

from dotenv import load_dotenv
load_dotenv()
from supabase import create_client
from hundredx import pptr_engine

client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

# ── 분류 맵 ──────────────────────────────────────────────────────────────────
CLASSIFICATIONS = {
    "000500": {
        "category": "전력_인프라",
        "sector_tag": "전선/전력기기",
        "industry": "전선케이블",
        "rationale": "AI 데이터센터 전력망 확충 수혜 — 전선 수요 급증, 8개월 10.5x",
    },
    "000650": {
        "category": "단기_테마_급등",
        "sector_tag": "운수/물류",
        "industry": "여객운수",
        "rationale": "버스/운수 관련 테마주 급등, 37일 내 12.4x (단기 과열 패턴)",
    },
    "007810": {
        "category": "빅테크_파트너",
        "sector_tag": "PCB/전자부품",
        "industry": "인쇄회로기판",
        "rationale": "AI 서버용 고다층 MLB PCB 수요 급증, 빅테크 공급 파트너, 1년 10.6x",
    },
    "017900": {
        "category": "단기_테마_급등",
        "sector_tag": "전자부품/광반도체",
        "industry": "LED/광전자",
        "rationale": "광반도체/LED 테마주 급등, 42일 내 10.1x (단기 과열 패턴)",
    },
    "047040": {
        "category": "수주잔고_선행",
        "sector_tag": "건설",
        "industry": "해외건설/EPC",
        "rationale": "중동·해외 EPC 대형 수주 누적으로 수주잔고 급증, 5.6개월 11.1x",
    },
    "049630": {
        "category": "정책_수혜",
        "sector_tag": "자동차부품",
        "industry": "알루미늄 다이캐스팅",
        "rationale": "방산/EV 관련 알루미늄 구조부품 정책 수혜, 4.5개월 10.0x",
    },
    "187660": {
        "category": "임상_파이프라인",
        "sector_tag": "바이오/제약",
        "industry": "바이오의약품",
        "rationale": "신약 임상 파이프라인 진행 + 바이오 계약, 8개월 16.4x",
    },
    "353200": {
        "category": "빅테크_파트너",
        "sector_tag": "PCB/반도체기판",
        "industry": "반도체 패키징기판",
        "rationale": "AI 서버·GPU용 HDI/MLB 고급 PCB 기판, 빅테크 공급망, 1년 10.5x",
    },
    "440110": {
        "category": "빅테크_파트너",
        "sector_tag": "반도체설계",
        "industry": "AI SSD 컨트롤러",
        "rationale": "AI 데이터센터 SSD 컨트롤러 반도체 설계, 빅테크 공급망, 1년 12.7x",
    },
}

print("[미분류 라이브러리 종목 카테고리 할당]")
print(f"{'티커':<8} {'기업':<20} {'카테고리':<22} {'근거'}")
print("-" * 100)

updated_cats = 0
pptr_updated = 0

for ticker, info in CLASSIFICATIONS.items():
    cat = info["category"]
    sector_tag = info["sector_tag"]
    industry = info["industry"]
    rationale = info["rationale"]

    # stocks 테이블에 sector_tag, industry 업데이트
    stk = client.table("stocks").select("name_kr").eq("ticker", ticker).execute()
    name = stk.data[0]["name_kr"] if stk.data else ticker

    # sector_tag이 비어있는 경우에만 업데이트
    stk_full = client.table("stocks").select("sector_tag").eq("ticker", ticker).execute()
    existing_sector = stk_full.data[0].get("sector_tag") if stk_full.data else None
    if not existing_sector:
        try:
            client.table("stocks").update({
                "sector_tag": sector_tag,
                "industry": industry,
            }).eq("ticker", ticker).execute()
        except Exception as e:
            pass  # industry 컬럼 없을 수도 있음

    # library stocks category 업데이트
    lib_rows = client.table("hundredx_library_stocks").select("*").eq("ticker", ticker).execute()
    if not lib_rows.data:
        print(f"  {ticker} {name:<20} - 라이브러리 없음, 건너뜀")
        continue

    for lib_row in lib_rows.data:
        current_cat = lib_row.get("category") or "미분류"
        if current_cat == "미분류":
            # category 업데이트
            try:
                client.table("hundredx_library_stocks").update({
                    "category": cat,
                }).eq("id", lib_row["id"]).execute()
                updated_cats += 1
                print(f"  {ticker} {name:<20} 미분류 → {cat:<22} | {rationale[:60]}")
            except Exception as e:
                print(f"  {ticker} {name:<20} 카테고리 업데이트 오류: {e}")
                continue

            # PPTR 재생성
            updated_row = dict(lib_row)
            updated_row["category"] = cat
            try:
                pptr_data = pptr_engine.generate_pptr(updated_row)
                client.table("hundredx_library_stocks").update({
                    "pptr_analysis": pptr_data,
                }).eq("id", lib_row["id"]).execute()
                pptr_updated += 1
                print(f"    ↳ PPTR 재생성 완료 ({len(str(pptr_data))} chars)")
            except Exception as e:
                print(f"    ↳ PPTR 재생성 오류: {e}")
        else:
            print(f"  {ticker} {name:<20} 이미 분류됨: {current_cat} (건너뜀)")

print(f"\n완료: 카테고리 {updated_cats}개 할당, PPTR {pptr_updated}개 재생성")

# ── 결과 확인 ─────────────────────────────────────────────────────────────────
print("\n[업데이트 후 라이브러리 현황]")
r = client.table("hundredx_library_stocks").select(
    "ticker, category, peak_multiplier"
).order("category").execute()
from collections import Counter
cat_counts = Counter(row.get("category") or "미분류" for row in (r.data or []))
for cat, cnt in sorted(cat_counts.items()):
    print(f"  {cat:<25} {cnt}개")
print(f"  총 {len(r.data or [])}개")
unclassified = [row["ticker"] for row in (r.data or []) if not row.get("category") or row["category"] == "미분류"]
if unclassified:
    print(f"  ⚠️  아직 미분류: {unclassified}")
else:
    print("  ✅ 모든 종목 분류 완료")
