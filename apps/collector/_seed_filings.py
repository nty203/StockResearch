"""시드 공시 데이터 삽입 — DART API 키 없을 때 로컬 테스트용.

2026-05 기준 실제 한국 시장 상황을 반영한 현실적인 공시 헤드라인.
(실제 수집이 아닌 테스트/검증 목적)
"""
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

# 현실적인 테스트 공시 데이터 (2026-05 기준)
SEED_FILINGS = [
    # ─── 빅테크_파트너 ─────────────────────────────────────────────────────
    {
        "ticker": "277810",  # 레인보우로보틱스
        "source": "SEED",
        "filing_type": "단일판매·공급계약체결",
        "filed_at": "2026-05-20T09:00:00+09:00",
        "url": "https://dart.fss.or.kr/test/001",
        "headline": "삼성전자 협동로봇 공급 계약 체결 및 지분 투자 유상증자 참여",
        "raw_text": "삼성전자가 당사에 유상증자 참여를 통해 지분을 취득하고, 산업용 협동로봇 공급 계약을 체결하였습니다.",
        "keywords": ["삼성전자", "지분 취득", "협동로봇", "유상증자 참여"],
        "parsed_amount": 500.0,
        "parsed_customer": "삼성전자",
    },
    {
        "ticker": "108490",  # 로보티즈
        "source": "SEED",
        "filing_type": "단일판매·공급계약체결",
        "filed_at": "2026-05-19T09:00:00+09:00",
        "url": "https://dart.fss.or.kr/test/002",
        "headline": "현대차그룹 물류 자동화 로봇 공급 계약 700억원 체결",
        "raw_text": "현대차그룹과 물류센터 자동화를 위한 로봇 공급 계약을 체결하였습니다. 계약금액 700억원.",
        "keywords": ["현대차", "로봇 공급", "공급계약"],
        "parsed_amount": 700.0,
        "parsed_customer": "현대차",
    },
    {
        "ticker": "007660",  # 이수페타시스
        "source": "SEED",
        "filing_type": "단일판매·공급계약체결",
        "filed_at": "2026-05-18T09:00:00+09:00",
        "url": "https://dart.fss.or.kr/test/003",
        "headline": "Microsoft Azure 하이퍼스케일 데이터센터용 AI 서버 고다층 MLB PCB 공급 계약 체결",
        "raw_text": "Microsoft Azure 데이터센터에 AI GPU 서버용 고다층 MLB 기판을 납품하는 장기 공급 파트너십 계약을 체결하였습니다.",
        "keywords": ["Microsoft", "하이퍼스케일", "AI 데이터센터", "고다층"],
        "parsed_amount": 1200.0,
        "parsed_customer": "Microsoft",
    },
    {
        "ticker": "042700",  # 한미반도체
        "source": "SEED",
        "filing_type": "단일판매·공급계약체결",
        "filed_at": "2026-05-21T09:00:00+09:00",
        "url": "https://dart.fss.or.kr/test/004",
        "headline": "NVIDIA HBM 패키징용 TC본더 공급 계약 확대 체결 2조원 규모",
        "raw_text": "NVIDIA의 차세대 HBM 메모리 패키징 라인 구축을 위해 TC본더 추가 공급 계약을 체결하였습니다. 2026년 하반기부터 납품 시작.",
        "keywords": ["NVIDIA", "HBM", "TC본더"],
        "parsed_amount": 20000.0,
        "parsed_customer": "NVIDIA",
    },
    # ─── 임상_파이프라인 ────────────────────────────────────────────────────
    {
        "ticker": "087010",  # 펩트론
        "source": "SEED",
        "filing_type": "주요사항보고서",
        "filed_at": "2026-05-20T09:00:00+09:00",
        "url": "https://dart.fss.or.kr/test/005",
        "headline": "GLP-1 기반 비만 치료 펩타이드 신약 임상 2상 진입 IND 승인",
        "raw_text": "GLP-1 수용체 작용제 기반 장기지속형 펩타이드 신약의 임상 2상 진입을 위한 IND 승인을 획득하였습니다.",
        "keywords": ["GLP-1", "임상 2상", "IND 승인"],
        "parsed_amount": None,
        "parsed_customer": None,
    },
    {
        "ticker": "000250",  # 삼천당제약
        "source": "SEED",
        "filing_type": "주요사항보고서",
        "filed_at": "2026-05-17T09:00:00+09:00",
        "url": "https://dart.fss.or.kr/test/006",
        "headline": "황반변성 치료제 바이오시밀러 점안제 임상 3상 완료 식약처 품목허가 신청",
        "raw_text": "라니비주맙 바이오시밀러 점안제의 임상 3상을 성공적으로 완료하고 식약처에 품목허가(NDA)를 신청하였습니다.",
        "keywords": ["황반변성", "바이오시밀러", "점안제", "임상 3상", "식약처"],
        "parsed_amount": None,
        "parsed_customer": None,
    },
    {
        "ticker": "196170",  # 알테오젠 (HLB)
        "source": "SEED",
        "filing_type": "주요사항보고서",
        "filed_at": "2026-05-15T09:00:00+09:00",
        "url": "https://dart.fss.or.kr/test/007",
        "headline": "ADC 항체 기술이전 글로벌 빅파마와 계약 체결 마일스톤 5000억원",
        "raw_text": "글로벌 빅파마와 ADC (항체약물접합체) 기술이전 계약을 체결하였습니다. 총 마일스톤 규모 5000억원, 선급금 500억원.",
        "keywords": ["ADC", "기술이전", "빅파마", "마일스톤"],
        "parsed_amount": 5000.0,
        "parsed_customer": "빅파마",
    },
    # ─── 공급_병목 ──────────────────────────────────────────────────────────
    {
        "ticker": "001570",  # 금양 (배터리 소재)
        "source": "SEED",
        "filing_type": "단일판매·공급계약체결",
        "filed_at": "2026-05-16T09:00:00+09:00",
        "url": "https://dart.fss.or.kr/test/008",
        "headline": "양극재 공급 부족 심화 속 국내 배터리 3사 공급 계약 체결 1조원 규모",
        "raw_text": "EV 배터리 양극재 수요 급증으로 LG에너지솔루션, 삼성SDI, SK온 3사와 장기 공급 계약을 체결하였습니다.",
        "keywords": ["양극재", "배터리 소재", "이차전지 소재"],
        "parsed_amount": 10000.0,
        "parsed_customer": "LG에너지솔루션",
    },
    {
        "ticker": "010140",  # 삼성중공업
        "source": "SEED",
        "filing_type": "수주공시",
        "filed_at": "2026-05-14T09:00:00+09:00",
        "url": "https://dart.fss.or.kr/test/009",
        "headline": "LNG운반선 4척 수주 계약 체결 1조8000억원 슈퍼사이클 지속",
        "raw_text": "글로벌 해운사로부터 LNG 운반선 4척을 1조8000억원에 수주하였습니다. 현재 수주잔고 30조원 달성.",
        "keywords": ["LNG운반선", "수주잔고", "슈퍼사이클"],
        "parsed_amount": 18000.0,
        "parsed_customer": "글로벌 해운사",
    },
    # ─── 정책_수혜 ──────────────────────────────────────────────────────────
    {
        "ticker": "298040",  # 효성중공업
        "source": "SEED",
        "filing_type": "단일판매·공급계약체결",
        "filed_at": "2026-05-13T09:00:00+09:00",
        "url": "https://dart.fss.or.kr/test/010",
        "headline": "IRA 배터리 보조금 수혜 대상 확정 북미 HVDC 변압기 공급 계약",
        "raw_text": "미국 인플레이션감축법(IRA) 배터리 보조금 수혜 대상으로 선정되었으며, 북미 HVDC 변압기 공급 계약도 체결하였습니다.",
        "keywords": ["IRA", "배터리 보조금", "HVDC", "변압기"],
        "parsed_amount": 3000.0,
        "parsed_customer": None,
    },
    {
        "ticker": "032820",  # 우리기술투자 or 관련 방산
        "source": "SEED",
        "filing_type": "수주공시",
        "filed_at": "2026-05-12T09:00:00+09:00",
        "url": "https://dart.fss.or.kr/test/011",
        "headline": "K-방산 폴란드 K-2 전차 추가 수주 2조원 방위산업 수출 확대",
        "raw_text": "폴란드 방위부와 K-2 전차 추가 수주 계약을 체결하였습니다. 방산 수출 지속 확대 중.",
        "keywords": ["방산", "K-2", "폴란드", "방위산업 수출"],
        "parsed_amount": 20000.0,
        "parsed_customer": "폴란드",
    },
    # ─── 수주잔고_선행 / 수익성_급전환 ───────────────────────────────────────
    {
        "ticker": "082740",  # HSD엔진
        "source": "SEED",
        "filing_type": "영업(잠정)실적공시",
        "filed_at": "2026-05-22T09:00:00+09:00",
        "url": "https://dart.fss.or.kr/test/012",
        "headline": "2026년 1분기 영업이익 흑자전환 데이터센터 발전엔진 수주 역대 최대",
        "raw_text": "2026년 1분기 영업이익이 전년 대비 흑자전환하였으며, AI 데이터센터용 힘센엔진 수주잔고가 역대 최대를 기록하였습니다.",
        "keywords": ["흑자전환", "AI 데이터센터", "힘센엔진", "수주잔고"],
        "parsed_amount": None,
        "parsed_customer": None,
    },
    {
        "ticker": "083450",  # GST (액체냉각)
        "source": "SEED",
        "filing_type": "단일판매·공급계약체결",
        "filed_at": "2026-05-22T09:00:00+09:00",
        "url": "https://dart.fss.or.kr/test/013",
        "headline": "Amazon AWS 데이터센터 액체냉각 시스템 독점 공급 계약 체결 5년 장기",
        "raw_text": "Amazon AWS와 AI 데이터센터용 액체냉각 시스템 독점 공급 5년 장기 계약을 체결하였습니다.",
        "keywords": ["Amazon", "AWS", "액체냉각", "AI 데이터센터"],
        "parsed_amount": 8000.0,
        "parsed_customer": "Amazon",
    },
    # ─── 원전/SMR ────────────────────────────────────────────────────────────
    {
        "ticker": "000150",  # 두산에너빌리티
        "source": "SEED",
        "filing_type": "수주공시",
        "filed_at": "2026-05-11T09:00:00+09:00",
        "url": "https://dart.fss.or.kr/test/014",
        "headline": "체코 두코바니 원전 주기기 공급 계약 체결 APR1000 3조원",
        "raw_text": "체코 두코바니 원전 2기 주기기 공급 계약을 체결하였습니다. APR1000 원자로 주기기 공급 계약 규모 3조원.",
        "keywords": ["원전", "체코", "두코바니", "APR"],
        "parsed_amount": 30000.0,
        "parsed_customer": "체코",
    },
    {
        "ticker": "005930",  # 삼성전자
        "source": "SEED",
        "filing_type": "단일판매·공급계약체결",
        "filed_at": "2026-05-21T09:00:00+09:00",
        "url": "https://dart.fss.or.kr/test/015",
        "headline": "HBM4 차세대 고대역폭 메모리 NVIDIA 단독 공급 계약 체결",
        "raw_text": "NVIDIA와 차세대 HBM4 고대역폭 메모리 단독 공급 계약을 체결하였습니다. AI GPU 플래그십 라인업에 탑재.",
        "keywords": ["HBM", "NVIDIA", "공급계약"],
        "parsed_amount": 50000.0,
        "parsed_customer": "NVIDIA",
    },
    {
        "ticker": "000660",  # SK하이닉스
        "source": "SEED",
        "filing_type": "단일판매·공급계약체결",
        "filed_at": "2026-05-20T09:00:00+09:00",
        "url": "https://dart.fss.or.kr/test/016",
        "headline": "HBM3E 12단 Microsoft AI 슈퍼컴퓨터 독점 공급 수주 8조원",
        "raw_text": "Microsoft AI 슈퍼컴퓨터 클러스터에 HBM3E 12단 제품을 독점 공급하는 계약을 체결하였습니다.",
        "keywords": ["HBM", "Microsoft", "AI 데이터센터"],
        "parsed_amount": 80000.0,
        "parsed_customer": "Microsoft",
    },
]

print(f"\n[시드 공시 데이터 삽입]")
print(f"삽입 대상: {len(SEED_FILINGS)}개 공시\n")

# Check which tickers exist in stocks table
tickers = list(set(f["ticker"] for f in SEED_FILINGS))
stocks_res = client.table("stocks").select("ticker, market").in_("ticker", tickers).execute()
existing_tickers = {r["ticker"] for r in (stocks_res.data or [])}
print(f"DB에 존재하는 종목: {len(existing_tickers)}/{len(tickers)}")

missing = set(tickers) - existing_tickers
if missing:
    print(f"DB 미존재 종목 (스킵): {missing}")

# Upsert filings
inserted = 0
skipped = 0
for f in SEED_FILINGS:
    if f["ticker"] not in existing_tickers:
        skipped += 1
        continue
    try:
        res = client.table("filings").insert(f).execute()
        inserted += 1
        print(f"  ✅ [{f['ticker']}] {f['headline'][:60]}")
    except Exception as e:
        print(f"  ❌ [{f['ticker']}] Error: {e}")
        skipped += 1

print(f"\n삽입: {inserted}개, 스킵: {skipped}개")

# Verify DB count
r = client.table("filings").select("*", count="exact").execute()
print(f"\n현재 DB 공시 총 수: {r.count}개")
