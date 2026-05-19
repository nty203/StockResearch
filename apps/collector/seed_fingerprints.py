import sys
# Ensure console printing is UTF-8 friendly
sys.stdout.reconfigure(encoding='utf-8')

from src.upsert import get_client
client = get_client()

# High-quality hand-crafted pre-rise fingerprints based on real historical trajectories (Blueprint DNA)
seed_fingerprints = [
    {
        "ticker": "298040",  # 효성중공업
        "category": "수주잔고_선행",
        "fingerprint": {
            "quant": {
                "bcr_at_signal": 1.8,               # 1.8 years of revenue backlog
                "backlog_yoy_pct": 55.0,            # 55% YoY backlog growth
                "opm_at_signal": 7.5,               # OPM jump
                "opm_prev": 2.1,                    # from low base
                "opm_delta_at_signal": 5.4,
                "revenue_growth_yoy": 28.0
            },
            "keywords": ["초고압 변압기", "변압기", "미국", "송전망", "쇼티지", "수주잔고", "공급계약", "증설"],
            "min_keyword_matches": 2,
            "sector_required": "전력기기",
            "amount_threshold_billions": 100.0,
            "auto_extracted": False,
            "description": "변압기 쇼티지와 전력망 교체 주기로 수주잔고 폭증 및 마진 Inflection 모델"
        }
    },
    {
        "ticker": "298040",  # 효성중공업 (수익성_급전환 카테고리 매칭용)
        "category": "수익성_급전환",
        "fingerprint": {
            "quant": {
                "opm_at_signal": 8.2,
                "opm_prev": 1.8,
                "opm_delta_at_signal": 6.4,
                "revenue_growth_yoy": 30.0
            },
            "keywords": ["변압기", "고부가", "마진 개선", "미국", "수주", "어닝 서프라이즈"],
            "min_keyword_matches": 2,
            "sector_required": "전력기기",
            "auto_extracted": False,
            "description": "저마진 구경제 제조업에서 고마진 초고압 변압기 전문사로 수익성 체질개선 모델"
        }
    },
    {
        "ticker": "086520",  # 에코프로
        "category": "공급_병목",
        "fingerprint": {
            "quant": {
                "bcr_at_signal": 1.5,
                "backlog_yoy_pct": 85.0,
                "opm_at_signal": 8.5,
                "opm_prev": 3.0,
                "opm_delta_at_signal": 5.5,
                "revenue_growth_yoy": 65.0
            },
            "keywords": ["배터리", "양극재", "EV", "수직계열화", "리사이클링", "전구체", "공급계약", "쇼티지"],
            "min_keyword_matches": 2,
            "sector_required": "배터리/소재",
            "amount_threshold_billions": 500.0,
            "auto_extracted": False,
            "description": "EV 패러다임 도래로 인한 양극재 및 핵심 원자재 공급 병목 폭발 모델"
        }
    },
    {
        "ticker": "042700",  # 한미반도체
        "category": "플랫폼_독점",
        "fingerprint": {
            "quant": {
                "opm_at_signal": 28.0,              # Exclusive monopoly margins
                "opm_prev": 12.0,
                "opm_delta_at_signal": 16.0,
                "revenue_growth_yoy": 55.0
            },
            "keywords": ["TC 본더", "TC Bonder", "HBM", "독점 공급", "독점계약", "SK하이닉스", "NVIDIA", "단독 공급"],
            "min_keyword_matches": 2,
            "sector_required": "반도체",
            "auto_extracted": False,
            "description": "HBM 고대역폭 메모리 검사 및 패키징 공정의 핵심 장비 표준 독점 모델"
        }
    },
    {
        "ticker": "042700",  # 한미반도체 (공급_병목 카테고리 매칭용)
        "category": "공급_병목",
        "fingerprint": {
            "quant": {
                "bcr_at_signal": 0.8,
                "opm_at_signal": 28.0,
                "revenue_growth_yoy": 55.0
            },
            "keywords": ["본더", "HBM", "공급 부족", "쇼티지", "설비 투자", "독점", "SK하이닉스"],
            "min_keyword_matches": 2,
            "sector_required": "반도체",
            "auto_extracted": False,
            "description": "글로벌 AI 반도체 공급망 병목 TC 본더 장비 쇼티지 수혜 모델"
        }
    },
    {
        "ticker": "012450",  # 한화에어로스페이스
        "category": "수주잔고_선행",
        "fingerprint": {
            "quant": {
                "bcr_at_signal": 3.2,               # Enormous military order backlog
                "backlog_yoy_pct": 45.0,
                "opm_at_signal": 8.0,
                "opm_prev": 4.5,
                "opm_delta_at_signal": 3.5,
                "revenue_growth_yoy": 25.0
            },
            "keywords": ["방산", "수주잔고", "K9 자주포", "폴란드", "천무", "수출 계약", "장기 공급"],
            "min_keyword_matches": 2,
            "sector_required": "방산",
            "amount_threshold_billions": 1000.0,
            "auto_extracted": False,
            "description": "글로벌 지정학 갈등 및 유럽 재무장으로 장기 대규모 수출 잔고형 재평가 모델"
        }
    },
    {
        "ticker": "012450",  # 한화에어로스페이스 (정책_수혜)
        "category": "정책_수혜",
        "fingerprint": {
            "quant": {
                "opm_at_signal": 8.0,
                "revenue_growth_yoy": 25.0
            },
            "keywords": ["수출", "국방", "정부", "폴란드", "방산 협력", "유럽", "계약"],
            "min_keyword_matches": 2,
            "sector_required": "방산",
            "auto_extracted": False,
            "description": "국가 안보 및 국방 강화 기조의 수혜 모델"
        }
    }
]

print("=== STARTING HAND-CRAFTED FINGERPRINT SEEDING ===")
success_count = 0

for item in seed_fingerprints:
    ticker = item["ticker"]
    category = item["category"]
    fingerprint = item["fingerprint"]
    
    try:
        # Check if the library stock entry exists
        res = client.table("hundredx_library_stocks")\
            .select("id, ticker, category")\
            .eq("ticker", ticker)\
            .eq("category", category)\
            .execute()
            
        if res.data:
            lib_id = res.data[0]["id"]
            # Update the pre_rise_signals
            client.table("hundredx_library_stocks")\
                .update({"pre_rise_signals": fingerprint})\
                .eq("id", lib_id)\
                .execute()
            print(f"  [SUCCESS] Seeded fingerprint for {ticker} ({category})")
            success_count += 1
        else:
            print(f"  [SKIP] Entry for {ticker} ({category}) not found in hundredx_library_stocks")
    except Exception as e:
        print(f"  [ERROR] Failed to seed for {ticker} ({category}): {e}")

print(f"\nDone: {success_count}/{len(seed_fingerprints)} fingerprints seeded successfully.")
