"""
DART API를 이용해 라이브러리 종목들의 분기/연간 재무제표를 백필.

- 대상: hundredx_library 종목 중 수익성_급전환(profit_inflect) 카테고리 보유 + 기타 전체
- 수집 범위: rise_date 기준 -3년 ~ +1년 (pre-rise 패턴 확보)
- 저장: financials_q 테이블 (fq 형식: '2022Q3', '2022Q2' 등)

Usage:
  python _backfill_dart_financials.py
  python _backfill_dart_financials.py --ticker 298040
  python _backfill_dart_financials.py --category profit_inflect
  python _backfill_dart_financials.py --all  # 전체 라이브러리
"""
import os, sys, io, time, re, logging, argparse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, 'src')
from dotenv import load_dotenv; load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)

import OpenDartReader
from supabase import create_client

SUPABASE_URL = os.environ['SUPABASE_URL']
SUPABASE_KEY = os.environ['SUPABASE_SERVICE_KEY']
DART_API_KEY = os.environ.get('DART_API_KEY', '')

if not DART_API_KEY:
    print("❌ DART_API_KEY not set in .env")
    sys.exit(1)

client = create_client(SUPABASE_URL, SUPABASE_KEY)
dart = OpenDartReader(DART_API_KEY)

# reprt_code 매핑
REPRT_CODES = {
    'Q1': '11013',   # 1분기
    'Q2': '11012',   # 반기보고서 (Q2 누적)
    'Q3': '11014',   # 3분기
    'Q4': '11011',   # 사업보고서 (연간)
}

# fs_div 우선순위: CFS(연결) > OFS(별도)
FS_DIV_PRIORITY = ['CFS', 'OFS']


def parse_amount(val: str) -> int | None:
    """'786,312,415,464' → 786312415464"""
    if not val or val.strip() in ('', '-', 'N/A'):
        return None
    try:
        return int(str(val).replace(',', '').replace(' ', ''))
    except ValueError:
        return None


def extract_financials(df, corp_code: str) -> dict | None:
    """
    finstate DataFrame에서 매출액, 영업이익 추출.
    연결재무제표(CFS) 우선, 없으면 별도(OFS).
    """
    if df is None or df.empty:
        return None

    for fs_div in FS_DIV_PRIORITY:
        subset = df[df['fs_div'] == fs_div] if 'fs_div' in df.columns else df
        if subset.empty:
            continue

        revenue = None
        op_income = None

        for _, row in subset.iterrows():
            nm = str(row.get('account_nm', ''))
            amt_str = str(row.get('thstrm_amount', ''))

            if nm == '매출액' and revenue is None:
                revenue = parse_amount(amt_str)
            elif nm in ('영업이익', '영업손익', '영업이익(손실)') and op_income is None:
                op_income = parse_amount(amt_str)

        if revenue is not None or op_income is not None:
            op_margin = None
            if revenue and op_income and revenue > 0:
                op_margin = round(op_income / revenue * 100, 2)
            return {
                'revenue': revenue,
                'op_income': op_income,
                'op_margin': op_margin,
                'fs_div': fs_div,
            }

    return None


def get_corp_code(ticker: str, name_kr: str) -> str | None:
    """티커 → DART corp_code 조회"""
    try:
        # 종목코드로 직접 조회
        corp_code = dart.find_corp_code(ticker)
        if corp_code:
            return corp_code
    except Exception:
        pass

    try:
        # 회사명으로 조회
        corp_code = dart.find_corp_code(name_kr)
        if corp_code:
            return corp_code
    except Exception:
        pass

    return None


def fetch_quarter(corp_code: str, year: int, quarter: str) -> dict | None:
    """특정 분기 재무제표 조회. quarter: 'Q1'|'Q2'|'Q3'|'Q4'"""
    reprt_code = REPRT_CODES[quarter]
    try:
        df = dart.finstate(corp_code, year, reprt_code=reprt_code)
        return extract_financials(df, corp_code)
    except Exception as e:
        logger.debug("DART fetch failed %s %dQ%s: %s", corp_code, year, quarter[-1], e)
        return None


def get_existing_fqs(ticker: str) -> set:
    """이미 DB에 있는 fq 목록"""
    res = client.table('financials_q').select('fq').eq('ticker', ticker).execute()
    return {r['fq'] for r in (res.data or [])}


def upsert_financials(ticker: str, fq: str, data: dict) -> bool:
    """financials_q에 upsert"""
    row = {
        'ticker': ticker,
        'fq': fq,
        'revenue': data.get('revenue'),
        'op_income': data.get('op_income'),
        'op_margin': data.get('op_margin'),
    }
    # net_income은 선택적으로 추가 가능
    try:
        client.table('financials_q').upsert(row, on_conflict='ticker,fq').execute()
        return True
    except Exception as e:
        logger.warning("Upsert failed %s/%s: %s", ticker, fq, e)
        return False


def backfill_ticker(ticker: str, name_kr: str, rise_date: str | None, force: bool = False) -> int:
    """
    한 종목의 재무 데이터 백필.
    rise_date 기준 -3년 ~ +1년 분기 데이터 수집.
    """
    logger.info("▶ %s (%s) rise=%s", ticker, name_kr, rise_date)

    corp_code = get_corp_code(ticker, name_kr)
    if not corp_code:
        logger.warning("  corp_code not found: %s (%s)", ticker, name_kr)
        return 0

    logger.debug("  corp_code=%s", corp_code)

    # 수집 범위 계산
    from datetime import datetime, timedelta
    if rise_date:
        try:
            rise_dt = datetime.fromisoformat(rise_date[:10])
        except ValueError:
            rise_dt = datetime.now()
    else:
        rise_dt = datetime.now()

    start_year = rise_dt.year - 3
    end_year = rise_dt.year + 1

    # 기존 fq 목록
    existing = get_existing_fqs(ticker) if not force else set()

    inserted = 0
    quarters = ['Q1', 'Q2', 'Q3', 'Q4']

    for year in range(start_year, end_year + 1):
        for quarter in quarters:
            fq = f"{year}{quarter}"
            if fq in existing:
                logger.debug("  skip %s (exists)", fq)
                continue

            # 미래 분기 스킵
            quarter_num = int(quarter[1])
            quarter_end_month = quarter_num * 3
            from datetime import date
            quarter_end = date(year, quarter_end_month, 28)
            if quarter_end > date.today():
                continue

            data = fetch_quarter(corp_code, year, quarter)
            time.sleep(0.3)  # DART rate limit

            if data and (data.get('revenue') or data.get('op_income')):
                if upsert_financials(ticker, fq, data):
                    inserted += 1
                    logger.info("  ✅ %s: rev=%s, opm=%s%%",
                                fq,
                                f"{data['revenue']:,}" if data.get('revenue') else 'N/A',
                                data.get('op_margin'))
            else:
                logger.debug("  ○ %s: no data", fq)

    return inserted


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ticker', help='특정 ticker만 처리')
    parser.add_argument('--category', help='특정 카테고리만 (예: profit_inflect)')
    parser.add_argument('--all', action='store_true', help='전체 라이브러리')
    parser.add_argument('--force', action='store_true', help='기존 데이터도 덮어쓰기')
    args = parser.parse_args()

    # 라이브러리 종목 조회
    query = client.table('hundredx_library_stocks').select(
        'ticker, category, rise_start_date'
    )

    if args.ticker:
        query = query.eq('ticker', args.ticker)
    elif args.category:
        query = query.eq('category', args.category)
    elif not args.all:
        # 기본: profit_inflect 카테고리 우선
        query = query.eq('category', 'profit_inflect')

    res = query.execute()
    library = res.data or []

    if not library:
        print("❌ 처리할 라이브러리 종목 없음")
        return

    # stocks 테이블에서 name_kr 조인
    tickers = list({r['ticker'] for r in library})
    stocks_res = client.table('stocks').select('ticker, name_kr').in_('ticker', tickers).execute()
    name_map = {s['ticker']: s.get('name_kr', '') for s in (stocks_res.data or [])}

    # 중복 ticker 제거 (한 ticker에 여러 카테고리 있을 수 있음)
    seen = set()
    unique = []
    for row in library:
        if row['ticker'] not in seen:
            seen.add(row['ticker'])
            unique.append({
                'ticker': row['ticker'],
                'name_kr': name_map.get(row['ticker'], row['ticker']),
                'rise_date': row.get('rise_start_date'),
                'category': row.get('category'),
            })

    print(f"\n📊 처리 대상: {len(unique)}개 종목 (카테고리 필터: {args.category or ('profit_inflect' if not args.all else '전체')})")
    print("=" * 60)

    total_inserted = 0
    for i, row in enumerate(unique, 1):
        print(f"\n[{i}/{len(unique)}] {row['ticker']} {row.get('name_kr', '')}")
        inserted = backfill_ticker(
            row['ticker'],
            row.get('name_kr', row['ticker']),
            row.get('rise_date'),
            force=args.force,
        )
        total_inserted += inserted
        print(f"  → {inserted}건 저장")

    print(f"\n{'='*60}")
    print(f"✅ 완료: 총 {total_inserted}건 upsert")


if __name__ == '__main__':
    main()
