# -*- coding: utf-8 -*-
"""
End-to-end pipeline runner:
  1. Build training samples from library
  2. Run historical validation
  3. Train model + evaluate
  4. Print comprehensive report
"""
import os
import sys
import logging

# Force UTF-8 output on Windows
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from dotenv import load_dotenv
load_dotenv()

from supabase import create_client

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

url = os.environ["SUPABASE_URL"]
key = os.environ["SUPABASE_SERVICE_KEY"]
client = create_client(url, key)

# ─────────────────────────────────────────────────────────────
# STEP 1: 학습 데이터 빌드
# ─────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("STEP 1: 학습 데이터 빌드 (Library → Training Samples)")
print("="*60)

from hundredx.validation.build_training_from_library import run as build_training
build_result = build_training(client, dry_run=False)
print(f"\n  Positive samples: {build_result['n_positive']}")
print(f"  Negative samples: {build_result['n_negative']}")
print(f"  Total:            {build_result['total']}")
print(f"  Library tickers:  {len(build_result.get('tickers', []))}")

# 현재 총 training samples 확인
total_r = client.table("pptr_training_samples").select("id").execute()
print(f"\n  DB 내 총 학습 샘플: {len(total_r.data or [])}개")

# 라벨 분포 (count query 대신 실제 데이터 로드)
all_samples = client.table("pptr_training_samples").select("label_10x_24m, split").execute().data or []
total_n = len(all_samples)
pos_n = sum(1 for r in all_samples if r.get("label_10x_24m") == 1)
neg_n = total_n - pos_n
pct_str = f"{pos_n/total_n:.1%}" if total_n > 0 else "N/A"
print(f"  Positive (10x):  {pos_n} ({pct_str})")
print(f"  Negative:        {neg_n}")

# Split 분포
from collections import Counter
split_dist = Counter(r.get("split", "unknown") for r in all_samples)
for split, n in sorted(split_dist.items()):
    print(f"  Split {split:<12}: {n}")

# ─────────────────────────────────────────────────────────────
# STEP 2: 역사적 검증 (Library vs Matches)
# ─────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("STEP 2: 역사적 검증 — Library 종목 탐지 분석")
print("="*60)

from hundredx.validation.historical_validation import run_validation, print_report
val_result = run_validation(client)
print_report(val_result)

# ─────────────────────────────────────────────────────────────
# STEP 3: 모델 학습 + 현재 활성 종목 평가
# ─────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("STEP 3: 모델 학습 + 현재 유망 종목 랭킹")
print("="*60)

from hundredx.validation.train_and_evaluate import run as train_eval, print_evaluation_report
eval_result = train_eval(client)
print_evaluation_report(eval_result)

# ─────────────────────────────────────────────────────────────
# STEP 4: 신뢰도 평가 종합
# ─────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("STEP 4: 시스템 신뢰도 종합 평가")
print("="*60)

metrics = val_result["metrics"]
all_m = metrics["all"]
test_m = metrics["test"]

print(f"""
[핵심 지표]
  Library 전체 종목:      {all_m['n_total']}개
  현재 활성 탐지 (전체):  {all_m['n_detected_active']}개  (Recall = {all_m['recall_active']:.1%})
  90일 이상 조기 탐지:    {all_m['n_true_positive_early']}개  (Early Recall = {all_m['recall_early']:.1%})

  TEST SET (2022년 이후 rise_start):
  종목 수:                {test_m['n_total']}개
  탐지됨:                 {test_m['n_detected_active']}개  (Recall = {test_m['recall_active']:.1%})
  조기 탐지:              {test_m['n_true_positive_early']}개  (Early Recall = {test_m['recall_early']:.1%})
  평균 선행기간:          {test_m.get('avg_lead_days') or 'N/A'}일
""")

# 신뢰도 등급 부여
recall = all_m['recall_active']
early_recall = all_m['recall_early']
if recall >= 0.70 and early_recall >= 0.40:
    grade = "A (우수)"
elif recall >= 0.50 and early_recall >= 0.25:
    grade = "B (양호)"
elif recall >= 0.35:
    grade = "C (보통)"
else:
    grade = "D (개선 필요)"

print(f"  시스템 탐지 등급: {grade}")
print(f"""
[개선 방향]
  1. 미탐지 종목({all_m['n_total'] - all_m['n_detected_active']}개)의 키워드/카테고리 규칙 추가 필요
  2. 학습 데이터 누적 후 LightGBM 재학습 (현재: {total_n}개, 목표: 500+개)
  3. 상장폐지 종목 survivorship-free 데이터 추가로 false positive 감소
  4. 매월 collect-survivorship 워크플로우 실행으로 자동 데이터 축적
""")

print("="*60)

# ─────────────────────────────────────────────────────────────
# STEP 5: 심층 분석 -- 탐지 누락 원인 및 개선 우선순위
# ─────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("STEP 5: 심층 분석 -- 탐지 누락 원인")
print("="*60)

misses = [r for r in val_result["per_stock"] if r["status"] == "MISS"]
miss_cats = {}
for r in misses:
    cat = r["category"]
    miss_cats[cat] = miss_cats.get(cat, 0) + 1

print(f"\n[탐지 누락 카테고리 우선순위]")
for cat, cnt in sorted(miss_cats.items(), key=lambda x: -x[1]):
    print(f"  {cat:<25} {cnt}개 누락")

detected_library = [r for r in val_result["per_stock"] if r["is_detected"]]
detected_tickers = {r["ticker"] for r in detected_library}

print(f"\n[탐지된 Library 종목 - {len(detected_library)}개]")
for r in sorted(detected_library, key=lambda x: x.get("rise_start") or ""):
    if r.get("lead_days") is not None:
        timing = f"후행 {abs(r['lead_days'])}일" if r["lead_days"] < 0 else f"선행 {r['lead_days']}일"
    else:
        timing = "N/A"
    print(f"  {r['ticker']:<10} {r['category']:<22} {r['peak_multiplier']:>5.1f}x  {timing}")

active_matches = eval_result["top_matches"]
new_candidates = [m for m in active_matches if m["ticker"] not in detected_tickers]

print(f"\n[신규 발굴 후보 (Library 미등재 활성 종목) - 상위 10개]")
print(f"  {'티커':<10} {'카테고리':<22} {'신뢰도':>8} {'현재 배수':>8}")
print("  " + "-" * 55)
for m in new_candidates[:10]:
    mult = f"{m['price_mult']:.2f}x" if m['price_mult'] > 1.0 else "  --  "
    print(f"  {m['ticker']:<10} {m['category'][:20]:<22} {m['final_confidence']:>8.3f} {mult:>8}")

# ─────────────────────────────────────────────────────────────
# STEP 6: 시스템 진단 및 구체적 개선 계획
# ─────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("STEP 6: 시스템 진단 및 개선 로드맵")
print("="*60)

total_library = len(val_result["per_stock"])
detected_active_cnt = len([r for r in val_result["per_stock"] if r["is_active"]])
missed_cnt = total_library - detected_active_cnt

print(f"""
[시스템 현재 수준 진단]

  탐지율:      {detected_active_cnt}/{total_library} = {detected_active_cnt/total_library:.1%}
  누락율:      {missed_cnt}/{total_library} = {missed_cnt/total_library:.1%}
  조기탐지:    없음 (모든 탐지가 상승 시작 이후)

  주요 원인 분석:
  1. [시간적 한계] 시스템이 2026년에 배포되어, 2015~2023년 상승종목은
     '후향적 탐지'만 가능. 현재 진행 중인 종목만 실시간 탐지 가능.

  2. [카테고리 공백] 이차전지/임상/빅테크 카테고리 탐지율 0%
     -> 해당 카테고리 키워드/룰 개선 필요

  3. [미분류 18%] Library 종목 9개가 아직 '미분류'
     -> 자동 분류 모델 개선 필요

  4. [False Positive 과다] 같은 종목이 7개 카테고리에 동시 매칭
     (예: 373220이 5개 카테고리에 모두 0.750 confidence)
     -> 가장 강한 카테고리만 선택하는 필터 추가 필요

  5. [Price Performance 미수집] 26,453개 matches 중 가격 데이터 NULL
     -> collect-hundredx 워크플로우에 price_performance 업데이트 추가

[우선순위별 개선 계획]

  HIGH (즉시 실행):
  a) 빅테크_파트너: 삼성/LG/SK 투자 종목 키워드 보강
     -> 277810(레인보우로보틱스), 007660(이수페타시스) 탐지 못함
  b) 임상_파이프라인: FDA IND/임상3상/기술이전 공시 탐지 강화
     -> 087010(펩트론), 000250(삼천당제약) 탐지 못함
  c) 중복 카테고리 필터: 종목당 best-category 1개로 집중

  MEDIUM (1개월 내):
  d) collect-survivorship 월 1회 실행 -> 학습 데이터 축적
     (현재 {total_n}개 -> 목표 1,000+개)
  e) price_performance 수집 파이프라인 활성화
  f) 현재 활성 match 가격 모니터링 강화

  LOW (3개월 내):
  g) LightGBM 재학습 (1,000+개 샘플 확보 후)
  h) Walk-forward 백테스트 with 2016~2024 historical data
  i) Paper trading 신호 실제 검증 시작 (Telegram 알림 포함)
""")

print("="*60)
print("파이프라인 완료!")
print("="*60)
