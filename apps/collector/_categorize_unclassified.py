"""미분류 라이브러리 17개 entries를 회사명 기반 수동 분류.

대다수가 2020-03 COVID 회복 시점 발견된 종목 — 그 시점 filings/news DB가 부족해
자동 분류 실패. 실제 사업 정체성 + 추후 성장 동인을 반영해 카테고리 할당.
"""
import os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, 'src')
from dotenv import load_dotenv; load_dotenv()
from supabase import create_client

client = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_KEY'])

# 회사명 기반 카테고리 매핑 — 명백한 thematic identity 기준
MANUAL_CATEGORIES = {
    "272210": "정책_수혜",         # 한화시스템 - 방산/위성
    "171090": "빅테크_파트너",      # 선익시스템 - 반도체 장비
    "056080": "빅테크_파트너",      # 유진로봇 - 협동로봇 (삼성·LG 협력)
    "006740": "단기_테마_급등",     # 영풍제지 - 소재 (테마성)
    "002710": "이차전지_소재",      # TCC스틸 - 양극재 동박
    "126340": "지주사_재평가",      # 두산 - 지주사
    "003670": "이차전지_소재",      # 포스코퓨처엠 - 양극재
    "079550": "정책_수혜",         # LIG넥스원홀딩스 - 방산
    "019175": "임상_파이프라인",    # 신풍제약우 - 바이오
    "034020": "전력_인프라",        # 두산에너빌리티 - 원전/전력
    "082740": "조선_슈퍼사이클",    # 한화엔진 - 선박엔진
    "036930": "빅테크_파트너",      # 주성엔지니어링 - 반도체 장비
    "058970": "빅테크_파트너",      # 엠로 - AI SaaS
    "247540": "이차전지_소재",      # 에코프로비엠 - 양극재 대표주
    "003535": "지주사_재평가",      # 한화우 - 지주
    "033100": "전력_인프라",        # 제룡전기 - 변압기
    "064350": "정책_수혜",         # 현대로템 - 방산/철도
}

updated = 0
for ticker, category in MANUAL_CATEGORIES.items():
    # 기존 row 조회
    rows = client.table("hundredx_library_stocks").select(
        "ticker, category, pre_rise_signals"
    ).eq("ticker", ticker).eq("category", "미분류").execute().data or []
    if not rows:
        print(f"  skip {ticker}: 미분류 row 없음 (이미 분류됨일 수 있음)")
        continue
    for row in rows:
        ps = row.get("pre_rise_signals") or {}
        # 카테고리만 변경, signals는 유지
        client.table("hundredx_library_stocks").update({
            "category": category,
        }).eq("ticker", ticker).eq("category", "미분류").execute()
        print(f"  ✅ {ticker} → {category}")
        updated += 1

print(f"\n총 {updated}건 분류 완료")
