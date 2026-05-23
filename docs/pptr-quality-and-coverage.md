# PPTR Quality Gate And Data Coverage

Last verified: 2026-05-23 KST

## Quality Gate

PPTR A-grade is intentionally strict. Do not lower these conditions just to make the dashboard show candidates.

Current verified state:

- Active KR universe checked: 2,776 KOSPI/KOSDAQ stocks
- Active PPTR rules: 17
- A-grade full PPTR matches: 0
- Noise categories excluded from active PPTR rules: `미분류`, `단기_테마_급등`

Interpretation:

- `0` A-grade matches means no current KR stock simultaneously satisfies one of the historical 100x PPTR rule sets.
- It does not mean there are no good stocks.
- It does mean the system should not invent A-grade candidates by weakening the rules.

Required behavior for future agents:

- Keep PPTR rules stock-specific. Do not merge all historical-stock conditions into one universal condition.
- A-grade must mean complete rule satisfaction.
- B/C-grade candidates must be stored and displayed separately from A-grade.
- Do not use volume-spike-only, `미분류`, or short-term theme rules as growth candidates.
- Do not allow a library stock to match its own PPTR rule.
- Near-misses require at least one specific signal such as keywords, amount, or BCR. Sector plus OPM alone is too generic.

## Current Data Coverage Caveat

The fast all-stock PPTR scan is fast because it uses data already in Supabase. It does not crawl the web live for every stock during the scan.

Current sources:

- DART filings via `apps/collector/src/filings_watch.py`
- SEC 8-K RSS via `apps/collector/src/filings_watch.py`
- RSS news via `apps/collector/src/news_rss.py`
- Financials via DART/SEC collectors
- Prices via `prices_daily`

Known blind spots:

- `news_rss.py` currently links news to stocks only when a ticker/code appears in the title or summary. Korean articles that mention only company names can be missed.
- RSS feeds are narrow: Hankyung finance, ChosunBiz, Yahoo Finance. Naver Finance/news search, DART full text, company IR pages, exchange disclosure feeds, and industry trade sources are not fully covered.
- DART filing watcher mostly stores headline-level data. `raw_text` is often null unless historical backfill or targeted parsing was run.
- PPTR scanner uses DB rows, not live web search, so a missing collector row means a missing PPTR signal.
- `_fetch_filings_2y` keeps only the latest two filings per ticker, which is good for clinical stage comparison but can miss older long-lead platform/adoption signals.

## Mandatory Check Before Saying “No A-Grade Exists”

Before reporting that no A-grade exists, run a coverage check and mention scope:

```powershell
cd apps/collector
uv run python -m src.hundredx.data_coverage
```

Then report:

- active KR stock count
- active PPTR rule count
- DART filing freshness
- news freshness
- `raw_text` coverage
- number of PPTR A-grade matches

If news or filings are stale, say “no A-grade in currently collected data,” not “no A-grade in the market.”

## Upgrade Priorities

1. Add company-name alias matching to `news_rss.py`.
2. Add more Korean sources: Naver Finance/news search, Maeil/Sedaily/Etoday/Infostock where legally and technically allowed.
3. Fetch and parse DART full text for PPTR-sensitive filings, not only headlines.
4. Store broad industry news as sector events even when no ticker is mentioned.
5. Add `data_coverage` output to `/settings` or `/library/stats`.
6. Keep A-grade strict; expand B/C-grade observability instead.
