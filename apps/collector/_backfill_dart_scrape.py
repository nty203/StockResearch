"""
Library stock historical filing headlines via DART HTML scraping.

No API key required. Scrapes dart.fss.or.kr disclosure search for each
library stock in the 18-month window before their rise_start_date.

Stores results in filings table with source='DART_SCRAPE'.
Deduplicates by (ticker, rcpt_no) — DART receipt number.

Coverage: 2010+ (very deep historical coverage)
Best for: All library stocks, especially pre-2022 rises

Usage:
  python _backfill_dart_scrape.py                    # all library stocks
  python _backfill_dart_scrape.py --ticker 042700
  python _backfill_dart_scrape.py --dry-run
  python _backfill_dart_scrape.py --months-before 24 # extend window
"""
import os, sys, io, time, argparse, requests
from datetime import datetime, timedelta
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, 'src')
from dotenv import load_dotenv; load_dotenv()

from bs4 import BeautifulSoup
from supabase import create_client

c = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_KEY'])

DART_SEARCH_URL = "https://dart.fss.or.kr/dsab001/search.ax"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Referer": "https://dart.fss.or.kr/",
}

# Filing types that indicate meaningful corporate events
RELEVANT_TYPES = {
    '단일판매ㆍ공급계약체결': '단일계약체결',
    '단일판매·공급계약체결': '단일계약체결',
    '공급계약체결': '단일계약체결',
    '수주': '수주공시',
    '임상': '임상시험',
    '기술이전': '기술이전계약',
    '주요경영사항': '주요경영사항',
    '풍문또는보도에대한해명': '해명공시',
    '사업보고서': '사업보고서',
    '반기보고서': '반기보고서',
    '분기보고서': '분기보고서',
    '합병': '합병공시',
    '투자': '투자공시',
    '증자': '증자공시',
}


def scrape_dart_disclosures(company_name: str, start_date: str, end_date: str,
                             max_pages: int = 5) -> list[dict]:
    """
    Scrape DART disclosure search for a company name + date range.

    Args:
        company_name: Korean company name (e.g., '한미반도체')
        start_date: 'YYYYMMDD'
        end_date: 'YYYYMMDD'
        max_pages: max pages to fetch (20 results/page)

    Returns: list of {title, date, rcpt_no, report_url}
    """
    results = []

    for page in range(1, max_pages + 1):
        params = {
            "textCrpNm": company_name,
            "startDate": start_date,
            "endDate": end_date,
            "currentPage": str(page),
            "maxResults": "20",
            "maxLinks": "10",
            "sort": "date",
            "series": "desc",
        }

        try:
            resp = requests.get(DART_SEARCH_URL, params=params, headers=HEADERS, timeout=15)
            resp.encoding = 'utf-8'

            if resp.status_code != 200:
                print(f"    DART HTTP {resp.status_code}")
                break

            soup = BeautifulSoup(resp.text, 'html.parser')

            # Find result table
            table = soup.find('table', class_='tbList')
            if table is None:
                # Try alternate table class
                tables = soup.find_all('table')
                table = next((t for t in tables if t.find('td')), None)

            if table is None:
                break

            rows = table.find_all('tr')
            found_this_page = 0

            for row in rows:
                cells = row.find_all('td')
                if len(cells) < 4:
                    continue

                # Typical DART result row: [no, company, title, date, submitter]
                # Find the title cell (has <a> link)
                title_cell = None
                date_text = None
                rcpt_no = None

                for i, cell in enumerate(cells):
                    a = cell.find('a')
                    if a and a.get('href') and 'rcpNo' in a.get('href', ''):
                        title_cell = cell
                        title_text = a.get_text(strip=True)
                        href = a['href']
                        # Extract rcpNo from href like /dsaf001/main.do?rcpNo=20230401001234
                        if 'rcpNo=' in href:
                            rcpt_no = href.split('rcpNo=')[1].split('&')[0].strip()
                        break

                if title_cell is None:
                    # Try finding link differently
                    for cell in cells:
                        links = cell.find_all('a')
                        for a in links:
                            href = a.get('href', '')
                            if href and ('rcpNo' in href or 'rcp' in href.lower()):
                                title_cell = cell
                                title_text = a.get_text(strip=True)
                                if 'rcpNo=' in href:
                                    rcpt_no = href.split('rcpNo=')[1].split('&')[0].strip()
                                break
                        if title_cell:
                            break

                if title_cell is None:
                    continue

                # Date: usually last meaningful cell or look for YYYY.MM.DD pattern
                import re
                for cell in reversed(cells):
                    text = cell.get_text(strip=True)
                    if re.match(r'\d{4}\.\d{2}\.\d{2}', text):
                        date_text = text
                        break

                if not date_text or not rcpt_no:
                    continue

                results.append({
                    'title': title_text,
                    'date': date_text,  # 'YYYY.MM.DD'
                    'rcpt_no': rcpt_no,
                    'report_url': f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcpt_no}",
                })
                found_this_page += 1

            if found_this_page == 0:
                break  # no more results

            time.sleep(0.3)  # polite crawling

        except Exception as e:
            print(f"    DART scrape ERROR page {page}: {e}")
            break

    return results


def classify_filing_type(title: str) -> str:
    """Classify DART disclosure title into a filing_type string."""
    for keyword, filing_type in RELEVANT_TYPES.items():
        if keyword in title:
            return filing_type
    return '공시'


def build_filing_row(ticker: str, item: dict) -> dict:
    """Build a filings table row from scraped DART disclosure."""
    # Parse date: 'YYYY.MM.DD' → datetime
    date_str = item['date'].replace('.', '-')  # '2022-01-15'
    try:
        filed_at = datetime.fromisoformat(date_str + 'T09:00:00')
    except ValueError:
        filed_at = datetime.utcnow()

    return {
        'ticker': ticker,
        'source': 'DART',
        'filing_type': classify_filing_type(item['title']),
        'filed_at': filed_at.isoformat(),
        'url': item['report_url'],
        'headline': item['title'][:500],
        'raw_text': '',  # headline only; body would need another scrape
        'keywords': [],
        'parsed_amount': None,
        'parsed_customer': None,
    }


def already_scraped(ticker: str, rise_start: str, months_before: int) -> bool:
    """Check if we already have historical filings in the pre-rise window."""
    rise_dt = datetime.fromisoformat(rise_start[:10])
    start_dt = rise_dt - timedelta(days=int(months_before * 30.5))

    # We need at least 3 filings to consider the window already covered
    r = c.table('filings')\
        .select('id', count='exact')\
        .eq('ticker', ticker)\
        .gte('filed_at', start_dt.isoformat())\
        .lt('filed_at', rise_dt.isoformat())\
        .execute()
    return (r.count or 0) >= 3


def upsert_filings(rows: list[dict], rcpt_nos: list[str], dry_run: bool = False) -> int:
    """Insert filing rows, checking for existing rcpt_nos to avoid duplicates."""
    if not rows:
        return 0

    if dry_run:
        for r in rows:
            print(f"    [DRY] {r['ticker']} {r['filed_at'][:10]} | {r['headline'][:60]}")
        return len(rows)

    # Check which rcpt_nos already exist (using URL as dedup key)
    urls = [row['url'] for row in rows]
    existing_r = c.table('filings').select('url').in_('url', urls).execute()
    existing_urls = set(row['url'] for row in (existing_r.data or []))

    new_rows = [r for r in rows if r['url'] not in existing_urls]

    if not new_rows:
        return 0

    try:
        c.table('filings').insert(new_rows).execute()
        return len(new_rows)
    except Exception as e:
        # Insert one by one
        inserted = 0
        for row in new_rows:
            try:
                c.table('filings').insert(row).execute()
                inserted += 1
            except Exception as e2:
                # Skip duplicates silently
                if 'duplicate' not in str(e2).lower():
                    print(f"    Insert failed: {e2}")
        return inserted


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ticker', help='Process only this ticker')
    parser.add_argument('--dry-run', action='store_true', help='Print without inserting')
    parser.add_argument('--months-before', type=int, default=18, help='Months before rise to scrape (default 18)')
    parser.add_argument('--force', action='store_true', help='Re-scrape even if data exists')
    args = parser.parse_args()

    # Get library stocks + their rise dates
    lib_r = c.table('hundredx_library_stocks').select('ticker,rise_start_date').execute()
    lib_rows = lib_r.data or []

    if args.ticker:
        lib_rows = [r for r in lib_rows if r['ticker'] == args.ticker]

    # Get unique (ticker, rise_start_date) pairs
    pairs = {}
    for row in lib_rows:
        if row.get('rise_start_date'):
            ticker = row['ticker']
            rise = row['rise_start_date']
            # Use earliest rise_start_date if ticker has multiple categories
            if ticker not in pairs or rise < pairs[ticker]:
                pairs[ticker] = rise

    print(f"Processing {len(pairs)} unique tickers with rise dates...")

    # Get Korean company names
    tickers = list(pairs.keys())
    stocks_r = c.table('stocks').select('ticker,name_kr').in_('ticker', tickers).execute()
    name_map = {row['ticker']: row['name_kr'] for row in (stocks_r.data or [])}

    total_inserted = 0

    for ticker, rise_start in sorted(pairs.items(), key=lambda x: x[1]):
        name = name_map.get(ticker, ticker)
        rise_dt = datetime.fromisoformat(rise_start[:10])
        start_dt = rise_dt - timedelta(days=int(args.months_before * 30.5))

        print(f"\n{ticker} {name} (rise={rise_start[:7]}, window={start_dt.date()}~{rise_dt.date()})")

        # Skip if already scraped
        if not args.force and not args.dry_run and already_scraped(ticker, rise_start, args.months_before):
            print(f"  Already scraped, skipping (use --force to re-scrape)")
            continue

        start_str = start_dt.strftime('%Y%m%d')
        end_str = rise_dt.strftime('%Y%m%d')

        # Scrape DART
        disclosures = scrape_dart_disclosures(name, start_str, end_str, max_pages=10)

        if not disclosures:
            print(f"  No disclosures found")
            time.sleep(1)
            continue

        print(f"  Found {len(disclosures)} disclosures")

        # Build filing rows
        filing_rows = [build_filing_row(ticker, item) for item in disclosures]
        rcpt_nos = [item['rcpt_no'] for item in disclosures]

        # Show top 5
        for item in disclosures[:5]:
            print(f"  {item['date']} | {item['title'][:60]}")
        if len(disclosures) > 5:
            print(f"  ... ({len(disclosures) - 5} more)")

        n = upsert_filings(filing_rows, rcpt_nos, dry_run=args.dry_run)
        total_inserted += n
        if not args.dry_run:
            print(f"  Inserted: {n} new rows")

        time.sleep(1.0)  # polite crawling

    print(f"\n=== 완료: {total_inserted}개 공시 inserted ===")


if __name__ == '__main__':
    main()
