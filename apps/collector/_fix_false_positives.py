"""DB 정리: 비바이오 종목의 임상_파이프라인 false positive + 과잉 dedup 문제 수정."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv()
from supabase import create_client
from datetime import datetime, timezone

client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
now = datetime.now(timezone.utc).isoformat()

NON_BIOTECH_SECTORS = [
    "조선", "엔진", "선박", "마린", "해양",
    "방산", "방위", "기계", "중공업",
    "전선", "전력기기", "변압기",
    "철강", "건설",
]

# ── 1. 비바이오 종목 + 임상_파이프라인 false positive ─────────────────────────
print("[1] 비바이오 종목의 임상_파이프라인 false positive 탐색")
clinical_matches = client.table("hundredx_category_matches").select(
    "id, ticker, category, confidence"
).eq("category", "임상_파이프라인").is_("exited_at", "null").execute()

false_positive_ids = []
for row in (clinical_matches.data or []):
    ticker = row["ticker"]
    stk = client.table("stocks").select("name_kr, sector_tag").eq("ticker", ticker).execute()
    if not stk.data:
        continue
    sector = (stk.data[0].get("sector_tag") or "").lower()
    name = stk.data[0].get("name_kr") or ticker
    if any(s in sector for s in NON_BIOTECH_SECTORS):
        print(f"  FP: {ticker} {name} sector={sector} conf={row['confidence']:.3f}")
        false_positive_ids.append(row["id"])

print(f"  총 {len(false_positive_ids)}개 false positive 발견")

# ── 2. 엔진/조선 종목의 비업종 카테고리 정리 ─────────────────────────────────
ENGINE_TICKERS = ["082740", "077970", "071970", "443060"]
KEEP_FOR_ENGINE = {"공급_병목", "정책_수혜", "수주잔고_선행", "수익성_급전환"}
REMOVE_FOR_ENGINE = {"임상_파이프라인", "빅테크_파트너", "플랫폼_독점", "단기_테마_급등"}

print("\n[2] 엔진/조선 종목 비업종 카테고리 정리")
engine_remove_ids = []
for ticker in ENGINE_TICKERS:
    matches = client.table("hundredx_category_matches").select(
        "id, ticker, category, confidence"
    ).eq("ticker", ticker).is_("exited_at", "null").execute()
    for row in (matches.data or []):
        cat = row["category"]
        stk = client.table("stocks").select("name_kr").eq("ticker", ticker).execute()
        name = stk.data[0]["name_kr"] if stk.data else ticker
        if cat in REMOVE_FOR_ENGINE:
            print(f"  REMOVE: {ticker} {name} -> {cat}")
            engine_remove_ids.append(row["id"])
        elif cat in KEEP_FOR_ENGINE:
            print(f"  KEEP:   {ticker} {name} -> {cat}")

all_remove_ids = list(set(false_positive_ids + engine_remove_ids))
print(f"\n총 {len(all_remove_ids)}개 제거 예정")

# ── 3. exited_at 설정으로 제거 (자동 실행) ─────────────────────────────────
removed = 0
for mid in all_remove_ids:
    try:
        client.table("hundredx_category_matches").update({
            "exited_at": now,
        }).eq("id", mid).execute()
        removed += 1
    except Exception as e:
        print(f"  오류 (id={mid}): {e}")

print(f"\n{removed}개 false positive 제거 완료")
