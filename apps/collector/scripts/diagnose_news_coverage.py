"""
뉴스 수집 커버리지 진단 스크립트 (ASCII-safe, paginated)
- prices_daily를 종목별 50개 배치로 조회 (Supabase 1000 row limit 우회)
- 최근 30일 급등 종목 vs 뉴스 커버리지 비교
"""
import os
import sys
from datetime import datetime, timedelta, timezone, date
from collections import defaultdict

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.upsert import get_client, retry_execute

LOOKBACK_DAYS = 30
SURGE_THRESHOLD_PCT = 10.0
TOP_N = 50

client = get_client()


def fetch_active_tickers():
    """활성 종목 ticker 목록."""
    res = retry_execute(
        lambda: client.table("stocks")
        .select("ticker, name_kr, name_en, market, sector_wics, sector_tag")
        .eq("is_active", True)
        .execute()
    )
    return res.data or []


def fetch_price_range_for_batch(tickers: list[str], cutoff: str) -> list[dict]:
    """종목 배치의 가격 데이터 조회."""
    res = retry_execute(
        lambda: client.table("prices_daily")
        .select("ticker, date, close")
        .in_("ticker", tickers)
        .gte("date", cutoff)
        .order("date", desc=False)
        .execute()
    )
    return res.data or []


def fetch_recent_price_surges(stocks: list[dict]):
    """활성 종목을 50개씩 배치 조회해 급등 종목 탐색."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).date().isoformat()
    print(f"\n[1] Price surge scan (from {cutoff}, batch 50)...")

    all_prices: dict[str, list] = defaultdict(list)
    tickers = [s["ticker"] for s in stocks]
    batch_size = 50

    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i+batch_size]
        rows = fetch_price_range_for_batch(batch, cutoff)
        for r in rows:
            all_prices[r["ticker"]].append((r["date"], r["close"]))
        if i % 500 == 0:
            print(f"    ... {i}/{len(tickers)} tickers processed")

    print(f"    -> {sum(len(v) for v in all_prices.values())} price records across {len(all_prices)} tickers")

    surges = []
    for ticker, prices in all_prices.items():
        if len(prices) < 5:
            continue
        prices.sort(key=lambda x: x[0])
        first_close = prices[0][1]
        last_close = prices[-1][1]

        # 최저점 탐색
        min_close = prices[0][1]
        min_date = prices[0][0]
        for d, c in prices:
            if c < min_close:
                min_close = c
                min_date = d

        # 최저점 이후 최고점
        max_close = 0.0
        max_date = min_date
        for d, c in prices:
            if d >= min_date and c > max_close:
                max_close = c
                max_date = d

        if min_close > 0 and max_close > min_close:
            surge_pct = (max_close - min_close) / min_close * 100
            if surge_pct >= SURGE_THRESHOLD_PCT:
                surges.append({
                    "ticker": ticker,
                    "surge_pct": round(surge_pct, 1),
                    "low_date": min_date,
                    "low_price": min_close,
                    "high_date": max_date,
                    "high_price": max_close,
                    "period_return_pct": round((last_close - first_close) / first_close * 100, 1)
                    if first_close > 0 else 0.0,
                })

    surges.sort(key=lambda x: x["surge_pct"], reverse=True)
    return surges[:TOP_N]


def fetch_news_for_tickers(tickers: list[str], start_date: str, end_date: str) -> dict[str, list]:
    if not tickers:
        return {}
    print(f"\n[2] News query ({start_date[:10]} ~ {end_date[:10]})...")

    news_map: dict[str, list] = defaultdict(list)
    chunk_size = 100
    for i in range(0, len(tickers), chunk_size):
        chunk = tickers[i:i+chunk_size]
        res = retry_execute(
            lambda: client.table("news")
            .select("ticker, title, published_at, source, url")
            .in_("ticker", chunk)
            .gte("published_at", start_date)
            .lte("published_at", end_date)
            .order("published_at", desc=True)
            .execute()
        )
        for r in (res.data or []):
            news_map[r["ticker"]].append(r)

    total = sum(len(v) for v in news_map.values())
    print(f"    -> {total} news records across {len(news_map)} tickers")
    return dict(news_map)


def fetch_pipeline_runs_summary() -> list[dict]:
    print("\n[0] Pipeline run history (news/filings)...")
    res = retry_execute(
        lambda: client.table("pipeline_runs")
        .select("stage, started_at, ended_at, status, rows_processed, error_msg")
        .in_("stage", ["news", "filings"])
        .order("started_at", desc=True)
        .limit(20)
        .execute()
    )
    return res.data or []


def fetch_overall_news_stats() -> dict:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=14)).date().isoformat()
    # 날짜 기준 count - Supabase는 GROUP BY 미지원, 전체 가져와서 파이썬 집계
    res = retry_execute(
        lambda: client.table("news")
        .select("published_at")
        .gte("published_at", cutoff)
        .limit(10000)
        .execute()
    )
    rows = res.data or []

    date_counts: dict[str, int] = defaultdict(int)
    for r in rows:
        dt = (r.get("published_at") or "")[:10] or "unknown"
        date_counts[dt] += 1

    return dict(sorted(date_counts.items()))


def main():
    print("=" * 70)
    print("NEWS COVERAGE DIAGNOSIS")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # 0. Pipeline run history
    pipeline_rows = fetch_pipeline_runs_summary()
    print(f"\n[Pipeline Run History - news/filings]")
    print(f"{'Stage':<12} {'Started':<22} {'Status':<10} {'Rows':>8}  Error")
    print("-" * 70)
    for r in pipeline_rows[:15]:
        started = (r.get("started_at") or "")[:19]
        status = r.get("status", "?")
        rows_p = r.get("rows_processed") or 0
        err = (r.get("error_msg") or "")[:30]
        print(f"{r['stage']:<12} {started:<22} {status:<10} {rows_p:>8}  {err}")

    # 0-1. Daily news stats
    news_stats = fetch_overall_news_stats()
    print(f"\n[Daily News Collection - last 14 days]")
    print(f"{'Date':<12} {'Count':>8}")
    print("-" * 28)
    for dt in sorted(news_stats.keys(), reverse=True):
        count = news_stats[dt]
        bar = "#" * min(count // 5, 40)
        print(f"{dt:<12} {count:>6}  {bar}")

    # 1. Active tickers
    print(f"\n[1b] Fetching active stock list...")
    stocks = fetch_active_tickers()
    meta_map = {s["ticker"]: s for s in stocks}
    print(f"     -> {len(stocks)} active stocks")

    # 2. Price surges (batched)
    surges = fetch_recent_price_surges(stocks)
    if not surges:
        print(f"\n[!] No surges found (threshold: {SURGE_THRESHOLD_PCT}%+, lookback: {LOOKBACK_DAYS}d)")
        print("    This may indicate insufficient price data in DB.")
        return

    surge_tickers = [s["ticker"] for s in surges]
    print(f"\n    Top {len(surges)} surge stocks found")

    # 3. News query
    cutoff_start = (
        datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS + 7)
    ).date().isoformat() + "T00:00:00Z"
    cutoff_end = datetime.now(timezone.utc).date().isoformat() + "T23:59:59Z"
    news_map = fetch_news_for_tickers(surge_tickers, cutoff_start, cutoff_end)

    # 4. Classify
    no_news = []
    low_news = []
    good_news = []

    for s in surges:
        ticker = s["ticker"]
        meta = meta_map.get(ticker, {})
        name = meta.get("name_kr") or meta.get("name_en") or "?"
        market = meta.get("market", "?")
        news_list = news_map.get(ticker, [])
        news_count = len(news_list)

        surge_news = [
            n for n in news_list
            if s["low_date"] <= (n.get("published_at") or "")[:10] <= s["high_date"]
        ]

        entry = {
            **s,
            "name": name,
            "market": market,
            "total_news": news_count,
            "surge_period_news": len(surge_news),
            "surge_news_samples": surge_news[:3],
        }

        if news_count == 0:
            no_news.append(entry)
        elif len(surge_news) == 0:
            low_news.append(entry)
        else:
            good_news.append(entry)

    sep = "=" * 70

    # ── Critical: zero news
    print(f"\n{sep}")
    print(f"[RED] CRITICAL - Surge but ZERO news collected: {len(no_news)} stocks")
    print(f"{'Ticker':<12} {'Name':<22} {'Mkt':<7} {'Surge%':>8}  Period")
    print("-" * 68)
    for e in no_news:
        print(f"{e['ticker']:<12} {str(e['name'])[:20]:<22} {e['market']:<7} {e['surge_pct']:>7.1f}%  "
              f"{e['low_date']} -> {e['high_date']}")

    # ── Yellow: news exists but not during surge
    print(f"\n[YELLOW] MISSED - News gap during surge period: {len(low_news)} stocks")
    print(f"{'Ticker':<12} {'Name':<22} {'Mkt':<7} {'Surge%':>8} {'AllNews':>8} {'InPeriod':>9}")
    print("-" * 70)
    for e in low_news:
        print(f"{e['ticker']:<12} {str(e['name'])[:20]:<22} {e['market']:<7} {e['surge_pct']:>7.1f}%  "
              f"{e['total_news']:>7}  {e['surge_period_news']:>8}")

    # ── Green: ok
    print(f"\n[GREEN] OK - News well covered: {len(good_news)} stocks")
    print(f"{'Ticker':<12} {'Name':<22} {'Surge%':>8} {'AllNews':>8} {'InPeriod':>9}")
    print("-" * 63)
    for e in good_news[:20]:
        print(f"{e['ticker']:<12} {str(e['name'])[:20]:<22} {e['surge_pct']:>7.1f}%  "
              f"{e['total_news']:>7}  {e['surge_period_news']:>8}")
        for n in e["surge_news_samples"][:2]:
            title = (n.get("title") or "")
            # encode-safe
            try:
                title = title.encode("utf-8").decode("utf-8")[:60]
            except Exception:
                title = "(encoding error)"
            pub = (n.get("published_at") or "")[:10]
            print(f"           [{pub}] {title}")

    # ── Detail: zero-news
    if no_news:
        print(f"\n{sep}")
        print("[DETAIL] Zero-news surge stocks (top 15)")
        for e in no_news[:15]:
            print(f"\n  [{e['ticker']}] {e['name']} ({e['market']})")
            print(f"  Surge {e['surge_pct']}%  {e['low_date']} {e['low_price']:,.0f}"
                  f" -> {e['high_date']} {e['high_price']:,.0f}")
            print("  Possible causes:")
            print("    - RSS feeds don't mention this ticker/company name")
            print("    - Unsupported media outlet (Yonhap, Newsis, Asia Economy, etc.)")
            print("    - Small-cap with very limited coverage")

    # ── Summary
    total = len(surges)
    print(f"\n{sep}")
    print("SUMMARY")
    print(f"  Analyzed: {total} surge stocks (last {LOOKBACK_DAYS}d, {SURGE_THRESHOLD_PCT}%+ from low)")
    print(f"  [GREEN]  OK (news in surge period):    {len(good_news):>3} ({len(good_news)/total*100:.1f}%)")
    print(f"  [YELLOW] Gap (news exists, not timed): {len(low_news):>3} ({len(low_news)/total*100:.1f}%)")
    print(f"  [RED]    Zero news:                    {len(no_news):>3} ({len(no_news)/total*100:.1f}%)")
    print(sep)

    if len(no_news) > total * 0.3:
        print(f"\n[!] WARNING: {len(no_news)/total*100:.0f}% have ZERO news.")
        print("    Recommended RSS feeds to add:")
        print("    - Yonhap:       https://www.yna.co.kr/RSS/economy.xml")
        print("    - Asia Economy: https://www.asiae.co.kr/rss/")
        print("    - Newsis:       https://www.newsis.com/rss/")
        print("    - eToday:       https://www.etoday.co.kr/rss.php")
        print("    - MoneyToday:   https://www.mt.co.kr/rss/mt_news.xml")
        print("    - Seoul Eco:    https://www.sedaily.com/RssService/RssFile?category=Economy")


if __name__ == "__main__":
    main()
