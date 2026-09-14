"""broker_reports.py — 네이버 금융 증권사 리포트 수집 모듈.

네이버 금융 종목분석 리포트를 크롤링하여 broker_reports 테이블에 저장합니다.
"""
import argparse
import logging
import time
import urllib.request
from datetime import datetime
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

from src.upsert import get_client, upsert_batch

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def fetch_page(page_num: int) -> list[dict]:
    url = f"https://finance.naver.com/research/company_list.naver?&page={page_num}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    results = []

    try:
        with urllib.request.urlopen(req) as response:
            html = response.read().decode("euc-kr", errors="replace")
            soup = BeautifulSoup(html, "html.parser")

            table = soup.select_one("table.type_1")
            if not table:
                logging.warning(f"No table found on page {page_num}")
                return results

            rows = table.select("tr")
            for row in rows:
                cols = row.select("td")
                if len(cols) < 6:
                    continue

                stock_name = cols[0].text.strip()
                title = cols[1].text.strip()
                
                # Parse ticker from the link
                a_tag = cols[0].select_one("a")
                ticker = ""
                if a_tag and "code=" in a_tag.get("href", ""):
                    ticker = a_tag["href"].split("code=")[1].split("&")[0]

                if not ticker:
                    continue

                firm = cols[2].text.strip()
                
                # Link to the report document itself (usually pdf) or the naver detail page
                # We will store the naver detail page link
                detail_a = cols[1].select_one("a")
                link = ""
                if detail_a and "href" in detail_a.attrs:
                    link = "https://finance.naver.com/research/" + detail_a["href"]

                raw_date = cols[4].text.strip() # Format: YY.MM.DD
                try:
                    # Naver uses YY.MM.DD
                    dt = datetime.strptime(raw_date, "%y.%m.%d")
                    date_str = dt.strftime("%Y-%m-%d")
                except ValueError:
                    continue

                results.append({
                    "ticker": ticker,
                    "name": stock_name,
                    "firm": firm,
                    "title": title,
                    "date": date_str,
                    "link": link
                })
    except Exception as e:
        logging.error(f"Error fetching page {page_num}: {e}")

    return results


def collect_broker_reports(pages: int = 5):
    """지정된 페이지 수만큼 증권사 리포트를 크롤링하여 저장합니다."""
    all_reports = []
    for p in range(1, pages + 1):
        logging.info(f"Fetching Naver Finance Research page {p}...")
        reports = fetch_page(p)
        if not reports:
            break
        all_reports.extend(reports)
        time.sleep(1) # Be nice to the server

    if not all_reports:
        logging.info("No reports found to save.")
        return

    # Deduplicate by unique key (ticker, firm, date, title) locally first
    unique_reports = []
    seen = set()
    for r in all_reports:
        key = (r["ticker"], r["firm"], r["date"], r["title"])
        if key not in seen:
            seen.add(key)
            unique_reports.append(r)

    logging.info(f"Collected {len(unique_reports)} unique reports. Upserting to Supabase...")

    client = get_client()
    total_inserted = upsert_batch(
        client=client,
        table="broker_reports",
        rows=unique_reports,
        on_conflict="ticker, firm, date, title"
    )
    
    if total_inserted > 0:
        logging.info(f"Successfully upserted {total_inserted} broker reports.")
    else:
        logging.warning("No rows inserted/upserted.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Collect broker reports from Naver Finance.")
    parser.add_argument("--pages", type=int, default=5, help="Number of pages to scrape (default 5)")
    args = parser.parse_args()

    collect_broker_reports(pages=args.pages)
