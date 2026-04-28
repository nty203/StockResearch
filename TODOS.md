# TODOS

> Items deferred from /plan-ceo-review on 2026-04-26 (100x Category Detection System)

---

## P2 — High Priority (Phase 2)

### [TODO-01] Category hit rate dashboard (`/hundredx/stats`)

**What:** Per-category validation page. For each of 7 categories, shows: "Detected N stocks matching in past 3 years. X achieved 100x+, Y achieved 30x+, avg lead time: Z months."

**Why:** Validates algorithm quality. Without this, we don't know if 수주잔고_선행 detector actually catches 80% of real 수주잔고 cases or 20%. Makes the system self-improving.

**Pros:** Bayesian confidence in each detector. Exposes systematic false positives early.

**Cons:** Requires running all 7 detectors backward over 3 years of historical `financials_q` and `filings` data per library stock. Price history needed for "did it achieve 100x?" check.

**Context:** Library must be populated first (006b seed SQL). The hit rate query joins `hundredx_library_stocks` (annotated rise dates) with historical detector outputs to compute per-category precision.

**Effort:** L (human) → M (CC+gstack)
**Priority:** P2 | **Depends on:** hundredx Phase 1 shipped + library populated

---

### [TODO-02] clinical_pipe.py stage-progression comparison

**What:** Upgrade `clinical_pipe.py` from keyword presence detection to cross-filing stage comparison: detect "IND→Phase 1", "Phase 1→Phase 2", "Phase 2→NDA" transitions across the 2 most recent filings.

**Why:** Keyword presence alone can't distinguish a company that filed an IND once two years ago from one that just advanced to Phase 2. Stage transitions are the actual catalyst.

**Pros:** Higher precision for biotech 100x detection. Reduces false positives from old/stale pipeline keywords.

**Cons:** DART uses inconsistent phase notation — requires handling "임상 1상 진입", "1/2상", "Phase I/II" variations. Risk of false negatives if phrasing doesn't match.

**Context:** Phase 1 ships keyword presence only. Measure false-positive rate in production (track: stocks flagged by clinical_pipe that didn't rise) before implementing stage comparison.

**Effort:** M (human) → S (CC+gstack)
**Priority:** P2 | **Depends on:** clinical_pipe Phase 1 shipped + 60 days of production data

---

## P3 — Nice to Have (Phase 3)

### [TODO-03] Research library admin UI

**What:** Web form at `/hundredx/library` to add new historical 100x stocks to `hundredx_library_stocks` table. Fields: ticker, category, earliest_signal_date, rise_start_date, peak_multiplier, notes.

**Why:** Currently requires manual SQL. As the library grows beyond 12 stocks (adding more cases from ongoing research), manual SQL becomes error-prone.

**Pros:** Makes library curation accessible. Enables faster library growth without DB access.

**Cons:** Adds an admin UI page. Must validate ticker against `stocks` table.

**Context:** Not urgent while library is small (12-20 stocks). Becomes valuable at 50+ stocks.

**Effort:** S (human) → S (CC+gstack)
**Priority:** P3 | **Depends on:** hundredx_library_stocks table deployed

---

### [TODO-04] US-market extension for category detectors

**What:** Extend all 7 category detectors to run on S&P1500 stocks (NASDAQ/NYSE) in addition to KOSPI/KOSDAQ. Requires: SEC filing text compatibility (already in `filings` table via 8-K), US sector_tag mapping, US financials from `financials_q`.

**Why:** The same patterns (backlog-lead, BigTech partnership, clinical pipeline) occur in US stocks. HD Electric US equivalent = Vertiv Holdings (2023 pattern). Missing this universe leaves ~1,500 high-quality candidates unchecked.

**Pros:** 2x+ universe coverage. US stocks have better financial data quality (SEC EDGAR via edgartools).

**Cons:** US sector_tag data not in schema. US financials use different field names (gross_margin vs op_margin as primary). Requires mapping work.

**Context:** Start KR-only (Phase 1). Validate detectors work before expanding universe. US extension is Phase 3.

**Effort:** L (human) → M (CC+gstack)
**Priority:** P3 | **Depends on:** KR Phase 1 validated and stable
