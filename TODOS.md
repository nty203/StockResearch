# TODOS

> Items deferred from /plan-ceo-review on 2026-04-26 (100x Category Detection System)
> + 2026-04-30 (Project reduction → 100x-only refocus)

---

## P1 — Top Priority (Reduction follow-ups)

### [TODO-05] Universe 확장 — KOSPI/KOSDAQ 전체 커버

**What:** universe.py가 현재 `is_active=True`를 KOSPI 상위 100개로 제한 (commit d3498da). 활성 universe를 KOSPI + KOSDAQ 전체(약 3,273 → 2,500+)로 확장. Daily collector의 prices/financials 부담을 평가하고 batch 사이즈/주기 조정.

**Why:** hundredx scanner가 universe의 약 3%만 스캔 중 — auto-discover가 정작 큰 multi-bagger를 놓침. Outside voice 지적: "코드를 줄여도 입력 set이 starve돼있으면 의미 없음." 100x 시스템의 효과는 universe 크기에 선형 비례.

**Pros:** discover.py의 자동 발견 종목 수 30배+ 증가 가능. fingerprint matching의 후보 풀 확장. "100배 후보를 못 찾는다"는 가장 큰 risk 해소.

**Cons:** GitHub Actions 시간 증가 (~5분 → ~30분 추정). DART API 호출량 증가. Supabase 저장 용량 증가. cf workflow timeout 60분 한계 점검 필요.

**Context:** 현재 universe.py가 왜 100개로 제한했는지(d3498da)는 free tier Supabase 부담 우려였을 가능성. hundredx scanner 자체는 BATCH_SIZE=50으로 처리 가능하므로 universe 확장 후 scanner 시간만 5x 증가. 30분 워크플로우 timeout이라 충분.

**Effort:** M (human ~3h) → S (CC+gstack ~30min — universe.py 로직 + 워크플로우 timeout 조정 + 테스트)
**Priority:** P1 | **Depends on:** PR1 reduction merged

---

### [TODO-06] hundredx-auto-populate workflow production 검증

**What:** GitHub Actions에서 `100x Auto-populate` workflow를 수동 실행 (workflow_dispatch). discover→backfill→extract 3단계가 실제 production에서 정상 작동하는지 확인:
1. discover가 universe로부터 100배+ 후보를 찾는지
2. backfill_history가 DART API로 historical 공시 가져오는지 (DART_API_KEY GitHub Secret 의존)
3. extract_signals가 백필된 데이터로부터 fingerprint를 산출하는지

**Why:** Outside voice 지적: 'auto_populate는 죽은 파이프라인 — DART_API_KEY가 GitHub Secret에만 있다는 가정에 검증 없음.' 매월 1일 자동 실행되지만 실제 결과(자동 발견 종목, 추출 시그널) 한 번도 production에서 확인 안 됨.

**Pros:** 'Step 1+2+3 자동 운영' 주장의 실제 동작 증거. 실패하는 단계 즉시 발견. DART rate limit, parsing edge case 등 실 데이터 이슈 노출.

**Cons:** DART API 호출 일 한도(20,000건/일) 일부 사용. 실패 시 디버그 비용.

**Context:** PR1 merge 직후 GitHub Actions 페이지에서 `100x Auto-populate` → Run workflow 클릭. 결과 로그에서 (a) discover 발견 수, (b) backfill 삽입 수, (c) extract 추출 fingerprint 수 확인.

**Effort:** S (human ~1h 검증) → S (CC+gstack ~15min — 워크플로우 dispatch + 결과 진단 스크립트)
**Priority:** P1 | **Depends on:** PR1 merge

---

### [TODO-07] hundredx 모듈 테스트 커버리지 확장

**What:** 현재 hundredx 테스트 = 82 cases (detector 52, scanner 11, fingerprint 11, timeline 8). 다음 5개 모듈은 테스트 0개:
- `discover.py` — 5y 가격 윈도우 max/trough 알고리즘
- `extract_signals.py` — 정량/키워드/카테고리 자동 추출
- `backfill_history.py` — DART historical 공시 백필
- `update_library.py` — 주간 latest_multiplier 갱신
- `auto_populate.py` — 3단계 orchestrator

**Why:** 100배 시스템이 프로덕트로 자리 잡으려면 회귀 방지 필수. Outside voice 지적: '2,312 LOC인데 82 tests = 28 LOC/test, critical path 위주만 커버.'

**Pros:** 회귀 방지. CI 안정성. 새 모듈 변경 시 기존 동작 보호. 알고리즘 의도 명확화 (테스트가 spec 역할).

**Cons:** 5개 모듈 합 ~25 신규 테스트 추정 (해피 패스 + 엣지 케이스). 시간 투자.

**Context:** test_fingerprint_match.py / test_timeline_match.py 패턴 참고. mock for Supabase client + DART API. 우선순위:
- discover.py — 알고리즘이 단순해서 테스트 가성비 최고 (해피 패스 + window edge cases)
- extract_signals.py — _categorize_from_filings 분류 정확도가 핵심
- update_library.py — 가격 fallback 로직 (이번 세션에서 발견된 버그 영역)

**Effort:** M (human ~6h) → S (CC+gstack ~45min — 5 모듈 × ~5 cases)
**Priority:** P1 | **Depends on:** PR1 merge

---

## P2 — Reduction follow-up

### [TODO-08] DB 테이블 drop PR2

**What:** 다음 production 마이그레이션 PR (`007_drop_legacy_tables.sql`) 작성:
```sql
DROP TABLE IF EXISTS screen_scores CASCADE;
DROP TABLE IF EXISTS agent_scores CASCADE;
DROP TABLE IF EXISTS analysis_queue CASCADE;
DROP TABLE IF EXISTS watchlist CASCADE;
DROP TABLE IF EXISTS backtest_runs CASCADE;
DROP TABLE IF EXISTS backtest_results CASCADE;
DROP TABLE IF EXISTS trigger_events CASCADE;  -- 만약 PR1에서 trigger_events도 정리됐다면
```

**Why:** PR1에서 코드 제거 후 사용처 0개인 테이블이 Supabase에 남음. 1주 운영 안정 확인 후 영구 제거. CASCADE로 의존 인덱스/제약 함께 제거.

**Pros:** Supabase 저장 용량 회수. 새 엔지니어가 'screen_scores가 뭔가요?' 질문 발생 안 함. 데이터 모델 명확.

**Cons:** **데이터 영구 손실.** 사전에 Supabase Dashboard에서 각 테이블 CSV export 권장 (히스토리 가치).

**Context:** PR1 deploy 시점 + **7일 이상** 경과 후 시작. 사전 점검:
1. Supabase Dashboard → SQL Editor로 각 테이블 row count 기록
2. CSV export (선택) — `\copy` 또는 Dashboard "Export" 버튼
3. `apply_migrations.py`로 실행

**Effort:** S (human ~2h, CSV export 포함) → S (CC+gstack ~10min)
**Priority:** P2 | **Depends on:** PR1 deploy + 7d ops stable

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
