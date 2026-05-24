"""Check which seed filing tickers were detected by the scanner."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv()
from supabase import create_client
from datetime import date, timedelta

client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

SEED_TICKERS = [
    ("277810", "레인보우로보틱스", "빅테크_파트너", "삼성전자 협동로봇"),
    ("108490", "로보티즈", "빅테크_파트너", "현대차 로봇"),
    ("007660", "이수페타시스", "빅테크_파트너", "Microsoft PCB"),
    ("042700", "한미반도체", "공급_병목", "NVIDIA TC본더"),
    ("087010", "펩트론", "임상_파이프라인", "GLP-1 임상"),
    ("000250", "삼천당제약", "임상_파이프라인", "황반변성 점안제"),
    ("196170", "알테오젠", "임상_파이프라인", "ADC 기술이전"),
    ("001570", "금양", "공급_병목", "양극재 공급부족"),
    ("010140", "삼성중공업", "공급_병목", "LNG운반선 슈퍼사이클"),
    ("298040", "효성중공업", "정책_수혜", "IRA HVDC"),
    ("032820", "방산회사", "정책_수혜", "K-방산 폴란드"),
    ("082740", "HSD엔진", "수익성_급전환", "데이터센터 발전엔진"),
    ("083450", "GST", "공급_병목", "AWS 액체냉각"),
    ("000150", "두산에너빌리티", "정책_수혜", "체코 원전"),
    ("005930", "삼성전자", "빅테크_파트너", "HBM4 NVIDIA"),
    ("000660", "SK하이닉스", "빅테크_파트너", "HBM3E Microsoft"),
]

print("=" * 80)
print(f"시드 공시 탐지 검증 (스캐너 실행 후)")
print("=" * 80)
print(f"{'종목':<8} {'이름':<16} {'기대 카테고리':<20} {'실제 탐지'}")
print("-" * 80)

found_count = 0
total_count = len(SEED_TICKERS)

for ticker, name, expected_cat, signal in SEED_TICKERS:
    # Check category_matches
    res = (
        client.table("hundredx_category_matches")
        .select("ticker, category, confidence, detected_at")
        .eq("ticker", ticker)
        .is_("exited_at", "null")
        .order("confidence", desc=True)
        .limit(5)
        .execute()
    )
    matches = res.data or []

    if not matches:
        status = "❌ 탐지 안됨"
    else:
        # Check if expected category is among matches
        cats = [(m["category"], m["confidence"]) for m in matches]
        matched_expected = [c for c, conf in cats if c == expected_cat]
        best_cat, best_conf = cats[0]
        if matched_expected:
            status = f"✅ {best_cat:<22} conf={best_conf:.3f}"
            found_count += 1
        else:
            status = f"⚠️  {best_cat:<22} conf={best_conf:.3f} (기대: {expected_cat})"
            found_count += 0.5  # partial credit

    print(f"  {ticker:<8} {name:<16} {expected_cat:<20} {status}")

print(f"\n탐지율: {found_count:.0f}/{total_count} ({found_count/total_count:.0%})")

# Show the most recent matches by detected_at
print(f"\n{'='*80}")
print("가장 최근 탐지된 매칭 (최근 24시간)")
print("-" * 80)
recent_res = (
    client.table("hundredx_category_matches")
    .select("ticker, category, confidence, detected_at")
    .is_("exited_at", "null")
    .order("detected_at", desc=True)
    .limit(20)
    .execute()
)
for m in (recent_res.data or []):
    dt = str(m["detected_at"])[:16]
    print(f"  [{dt}] {m['ticker']:<8} {m['category']:<25} conf={m['confidence']:.3f}")

# Show category distribution (full)
print(f"\n{'='*80}")
print("카테고리별 전체 분포")
print("-" * 80)
all_res = (
    client.table("hundredx_category_matches")
    .select("category, confidence")
    .is_("exited_at", "null")
    .execute()
)
from collections import Counter, defaultdict
cat_counts = Counter(m["category"] for m in (all_res.data or []))
cat_conf_sum = defaultdict(float)
cat_conf_cnt = defaultdict(int)
for m in (all_res.data or []):
    cat_conf_sum[m["category"]] += m["confidence"]
    cat_conf_cnt[m["category"]] += 1

print(f"  {'카테고리':<25} {'수':>6}  {'평균 신뢰도':>10}")
for cat, cnt in sorted(cat_counts.items(), key=lambda x: -x[1]):
    avg_conf = cat_conf_sum[cat] / cat_conf_cnt[cat] if cat_conf_cnt[cat] else 0
    print(f"  {cat:<25} {cnt:>6}  {avg_conf:>10.3f}")

print(f"\n총 활성 매칭: {sum(cat_counts.values()):,}개")
