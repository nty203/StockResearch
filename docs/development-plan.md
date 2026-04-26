# 10배 상승주 조기 발굴 프로그램 — 개발 계획서

## Context (왜 만드는가)

두 개의 리서치 리포트(1부: 25종목 역산 분석 + 설계서, 2부: 55종목 확장 + 필터 업데이트)를 실행 가능한 웹 기반 도구로 구현한다. 리포트의 결론 — **"공급 병목 × 빅테크 CAPEX × 영업이익률 급등 교집합에서 10배가 나오고, 그 신호는 반드시 DART/SEC 공시에 선행 노출된다"** — 을 자동 포착하는 깔때기 시스템을 만든다. 최종 목표는 다음 3가지이다:

1. **정량 스크리닝 자동화**: 리포트 3부(한국) + 3-C(미국) 필터 + 2부 8-1의 업데이트된 필터를 매일 KOSPI/KOSDAQ/S&P1500 유니버스에 적용해 30~50 후보로 축소
2. **정성 분석 에이전트 연동**: 리포트 4부 5종 프롬프트 + 2부 9부 3종 프롬프트를 "파일 기반 인박스/아웃박스" 방식으로 Claude Code 같은 에이전트 AI에 위임 (API 키 없이 운용)
3. **단일 화면 대시보드**: 종목별 10배 점수, 트리거 이벤트 타임라인, 워치리스트 전환 알림, 주기적 업데이트 스케줄 설정을 한 화면에서 관리

## 배포 아키텍처 (사용자 선택 반영)

```
GitHub Repo (monorepo)
  ├── apps/web/          ← Next.js 14 (App Router)      → Cloudflare Pages 자동 배포
  ├── apps/collector/    ← Python 데이터 수집 스크립트   → GitHub Actions 크론 실행
  ├── packages/shared/   ← TypeScript 타입·스키마
  └── .github/workflows/ ← 스케줄 Actions (매일/매시간)

Supabase (ap-northeast-2)
  ├── postgres: 종목·재무·점수·이벤트·워치리스트·설정
  ├── storage: 분석 큐/결과 md 번들, 리포트 PDF
  └── auth: 비활성화 (단일 사용자)

Cloudflare Pages (Next.js)
  ├── / (대시보드)
  ├── /watchlist, /stocks/[ticker], /signals, /queue, /settings
  └── /api/* (Supabase 읽기/쓰기 프록시)

Agent Loop (로컬)
  Claude Code → Supabase Storage에서 `/analysis_queue/{ticker}.md` 다운로드
              → 프롬프트 실행 → `/analysis_results/{ticker}.json` 업로드
              → 웹 UI가 polling으로 자동 갱신
```

**핵심 결정 근거**:
- FastAPI는 Cloudflare Workers/Pages 네이티브 실행이 어려워 탈락. Next.js API Routes가 Cloudflare Pages Functions로 변환됨
- Python 데이터 수집은 GitHub Actions에서 크론 실행 → Supabase에 쓰기. 서버리스 비용 0원
- 인증은 단일 사용자이므로 생략하되, Next.js middleware에서 Cloudflare Access로 추후 보호 가능

## 기술 스택

| 레이어 | 선택 | 근거 |
|---|---|---|
| Frontend | Next.js 14 App Router + React 18 + TypeScript | Cloudflare Pages 최적화, SSR/SSG 자유 |
| UI 라이브러리 | Tailwind CSS + shadcn/ui + Recharts/Tremor | 대시보드·차트·테이블 빠른 구축 |
| 데이터 fetch | Supabase JS client + TanStack Query | 실시간 구독(Postgres Realtime) 활용 |
| Backend API | Next.js Route Handlers (Cloudflare Pages Functions) | Python 불필요, TS 단일 언어 |
| DB | Supabase Postgres + Row Level Security | 무료 500MB, pg_cron 지원 |
| File Storage | Supabase Storage | md 번들·리포트 저장 |
| 데이터 수집 | Python 3.11 + `OpenDartReader` + `yfinance` + `sec-api` + `FinanceDataReader` + `feedparser` | 리포트 5-A/5-B/5-E 레시피 그대로 |
| 스케줄러 | GitHub Actions schedule (`cron:`) + Supabase pg_cron(백업) | 무료 분당 실행, 타임존 설정 가능 |
| 에이전트 AI | 사용자 로컬 Claude Code (또는 호환 에이전트) | API 키 불필요, 파일 기반 |
| 알림 | Telegram Bot API + 웹 푸시(선택) | 무료, 단일 사용자 적합 |

## 데이터 모델 (Supabase Postgres)

```sql
-- 유니버스 & 종목 메타
stocks(id, ticker, market, name_kr, name_en, sector_wics, industry, is_active, ...)

-- 일봉 시세 (compressed, 2년치 유지)
prices_daily(ticker, date, open, high, low, close, volume, adj_close)
-- INDEX: CREATE UNIQUE INDEX ON prices_daily(ticker, date);

-- 분기 재무 (DART/SEC 공시 정제)
-- fq 형식: 'YYYYQ[1-4]' (예: '2023Q1') — DART·SEC 공통 정규화 필수
financials_q(ticker, fq, revenue, op_income, net_income, op_margin,
             roe, roic, fcf, debt_ratio, interest_coverage, ...)
-- INDEX: CREATE UNIQUE INDEX ON financials_q(ticker, fq);

-- 수주·주요 공시
filings(id, ticker, source, filing_type, filed_at, url, headline,
        raw_text, keywords[], parsed_amount, parsed_customer, ...)
-- INDEX: CREATE INDEX ON filings(ticker, filed_at DESC);

-- 뉴스 (RSS 수집)
news(id, ticker, source, published_at, url, title, summary, lang)
-- INDEX: CREATE INDEX ON news(ticker, published_at DESC);

-- 1차 정량 점수 (매일 전체 재계산 — 2-pass: raw → percentile)
-- passed: 필수 필터 5개(시총·거래대금·매출성장·수주잔고·부채비율) 모두 통과 시 true
screen_scores(ticker, run_date,
              growth, momentum, quality, sponsorship, value, safety, size,
              market_gate, score_10x, percentile, passed, failed_filters[])
-- INDEX: CREATE UNIQUE INDEX ON screen_scores(ticker, run_date);

-- 2차 정성 점수 (에이전트 결과)
-- agent_result_schema: {demand_score, moat_score, trigger_score,
--   narrative_md, risks_md, bull_bear_ratio} — Pydantic 검증 필수
agent_scores(ticker, run_date, prompt_type,
             demand_score, moat_score, trigger_score, narrative_md,
             risks_md, bull_bear_ratio, agent_model, created_at)
-- INDEX: CREATE UNIQUE INDEX ON agent_scores(ticker, run_date, prompt_type);

-- 트리거 이벤트 카탈로그 (리포트 5부 15개 유형)
trigger_events(id, ticker, event_type, detected_at, confidence,
               source_filing_id, matched_keywords[], summary)
-- INDEX: CREATE INDEX ON trigger_events(ticker, detected_at DESC);

-- 워치리스트
watchlist(id, ticker, status, added_at, notes,
          target_price, stop_loss, position_size_plan)

-- 분석 큐 (에이전트 인박스)
-- status: PENDING → CLAIMED → COMPLETED | FAILED | INVALID
-- UNIQUE(ticker, prompt_type) WHERE status IN ('PENDING','CLAIMED')
-- claimed_at + 48h 경과 시 pg_cron으로 PENDING 복귀
analysis_queue(id, ticker, prompt_type, status, created_at,
               claimed_at, storage_path_prompt, storage_path_result, claimed_by)

-- 파이프라인 실행 로그 (settings 체크리스트 데이터 소스)
-- stage: 'universe'|'prices'|'financials'|'filings'|'news'|'scores'|'queue'|'notify'
pipeline_runs(id, stage, started_at, ended_at, status,
              rows_processed, error_msg, github_run_id)

-- 사용자 설정 (Python 스크립트 startup 시 fetch)
-- Python: settings = supabase.table('settings').select('*').execute()
settings(key, value_json, updated_at)

-- 실패 사례 학습 DB (리포트 2부 3부) — 한 종목이 여러 번 실패 가능하므로 id PK
failure_cases(id, ticker, peak_at, peak_price, trough_at, trough_price,
              early_signals[], lesson_md)
```

## 구현 단계 (MVP 14주)

### Phase 0 — 저장소 부트스트랩 (1주)
- `package.json` 모노레포 (pnpm workspaces), `.nvmrc`, `pyproject.toml` (uv)
- **`@cloudflare/next-on-pages` + `wrangler` 설치** — Next.js/Cloudflare 어댑터 (Day 0 필수)
- `wrangler.toml` 설정 + 모든 Route Handler에 `export const runtime = 'edge'` 템플릿 추가
- Supabase 프로젝트 생성 + CLI 설치 (`pnpm add -D supabase`)
- 위 테이블 마이그레이션 (`supabase/migrations/001_init.sql`) + `npx supabase db push`
- **다운 마이그레이션** (`supabase/migrations/001_rollback.sql`) 함께 작성
- Cloudflare Pages 프로젝트 연결 + 환경변수 설정:
  ```
  Cloudflare env: SUPABASE_URL, SUPABASE_SERVICE_KEY, TELEGRAM_BOT_TOKEN, GITHUB_PAT, GITHUB_REPO
  GitHub Secrets: SUPABASE_URL, SUPABASE_SERVICE_KEY, DART_API_KEY, GITHUB_PAT
  ```
  ⚠️ Telegram 토큰은 DB settings 테이블이 아닌 Cloudflare env var로 관리
- GitHub Actions 스켈레톤 (`.github/workflows/collect-daily.yml`, `collect-hourly.yml`)
  - ⚠️ 모든 workflow yml에 `workflow_dispatch:` 트리거 명시 필수 — `/settings` 수동 재실행 버튼이 GitHub API `workflow_dispatch` 호출하므로, 선언 없으면 404 오류
- **Public repo 설정** (GitHub Actions 무료 무제한 사용을 위해)

### Phase 1 — 데이터 파이프라인 (3주)
파일: `apps/collector/src/`
- `universe.py` — KOSPI+KOSDAQ (KRX 종목코드 CSV) + S&P1500 구성
- `prices.py` — yfinance 배치 (US) + FinanceDataReader (KR)
- `financials_dart.py` — OpenDartReader로 분기별 재무 수집
- `financials_sec.py` — `edgartools` 라이브러리로 EDGAR XBRL 파싱 (`set_identity('name email')` 필수, rate limit 10 req/sec 준수, sleep 0.1초 삽입)
- `filings_watch.py` — DART `list(kind='B')` + SEC EDGAR 8-K RSS 키워드 필터 (리포트 5-E 레시피 그대로)
- `news_rss.py` — 한경·조선비즈·Yahoo Finance RSS
- `upsert.py` — Supabase 배치 upsert 공통 유틸
- ⚠️ **GitHub Actions에서 Supabase 연결 시 pooler URL 사용** (`project.pooler.supabase.com:6543`) — free tier 직접 연결 제한(5개) 초과 방지. `SUPABASE_DB_URL` secret에 pooler URL 저장
- ⚠️ **`apps/collector/src/` 하위 모든 패키지 디렉토리에 `__init__.py` 필요** — `uv run python -m src.prices` 모듈 로딩 필수

### Phase 2 — 정량 스크리닝 엔진 + 테스트 (2주)
파일: `apps/collector/src/screening/`
- `filters_kr.py` — 리포트 3-B의 22개 필터 (f01~f22). **필수 필터 5개(f01·f02·f03·f08·f09) ALL-AND, 나머지 17개는 점수 기여.**
- `filters_us.py` — 리포트 3-C의 20개 필터 (us01~us20). 동일 구조.
- `score.py` — 리포트 6-B 8개 카테고리 가중합 (Growth 28 / Momentum 22 / …). **2-pass 구조: 1) 전체 종목 raw 계산, 2) universe 내 percentile 변환** (`pandas.rank(pct=True)`)
- `peak_risk.py` — "PSR 20배+ · FCF 3년 음수 · 내부자 매도 > 유통주 5%" 동시 충족 시 `-30점 페널티`
- `settings_loader.py` — **Supabase에서 설정 fetch 공통 유틸** (`from settings_loader import load_settings; cfg = load_settings(supabase)`)
- `backtest.py` — 2020~2024 point-in-time 역산 검증 (한국: FinanceDataReader 상폐주 지원, US: Stooq CSV 사용)
- 매일 06:00 KST 배치로 `screen_scores` 테이블 갱신 + `pipeline_runs` 기록
- **테스트 (`apps/collector/tests/`)** — Phase 2와 함께 작성 (pytest):
  - `test_filters_kr.py`: 효성중공업 2023Q1 → 22개 필터 통과 확인 (역산 검증)
  - `test_filters_kr.py`: 에코프로 2023Q4 peak data → `peak_risk` 페널티 -30점 적용 확인
  - `test_filters_us.py`: US mock 종목(필터 통과 기준) → 20개 필터 결과 확인
  - `test_score.py`: 5종목 mock → percentile 0~100 범위, 가중합 ≤ 100, market_gate 0.7 적용 확인
  - `test_upsert.py`: 동일 데이터 2회 upsert → 중복 행 없음 확인 (idempotency)
  - `test_settings_loader.py`: Supabase mock → settings key fetch + override 값 반영 확인
- **`pandas-ta>=0.3`** 의존성 추가 (RS·MA·거래량 지표 계산용)

### Phase 3 — 트리거 이벤트 탐지 (1주)
파일: `apps/collector/src/triggers/`
- `classifier.py` — 리포트 5부 15개 트리거 유형 룰베이스 분류
  - 유형 1 (빅테크 단일 수주): 키워드 `["MSFT", "Google", "Amazon", "Oracle", "PPA"]` + 금액 파싱
  - 유형 2 (CAPEX 증설): `["증설", "신공장", "CAPEX", "ground breaking"]` + 매출 대비 비율
  - 유형 3 (글로벌 메가계약): 국가명 + 조 단위 + 방산·원전 섹터
  - ...15개까지
- `golden_signal.py` — 리포트 2-D 8선의 공통구조 "수주+빅네임+CAPEX" 3종 중 2개↑ 동시 탐지 시 `golden=true`
- 탐지 즉시 `trigger_events` 삽입 + 워치리스트 자동 후보 추가 (초기 status=`'candidate'` → 사용자 승인 시 `'yellow'` → 조건 충족 시 `'green'`)
- **테스트 (Phase 3에 추가)**:
  - `test_classifier.py`: "SK하이닉스 600억 TC본더 수주" 텍스트 → `trigger_type='단일_수주'` 확인
  - `test_golden_signal.py`: 수주+빅네임+CAPEX 3종 중 2종 동시 → `golden=True`, 1종만 → `golden=False` 확인

### Phase 4 — 에이전트 큐 & 파일 인박스/아웃박스 (1주)
파일: `apps/collector/src/queue/` + `apps/web/app/api/queue/`
- `enqueue.py` — 정량 점수 ≥ 65 or 골든 시그널 탐지 종목을 큐에 추가
  - 임계값 65는 `settings` 테이블에서 `settings_loader.py`로 fetch (하드코딩 금지)
- 큐 아이템 생성 시 자동으로 프롬프트 번들 md 생성 후 Supabase Storage 업로드
  - `analysis_queue/{ticker}_{prompt_type}_{run_id}.md` (입력 번들: 리포트 4-1~4-5 + 2부 9-1~9-3 프롬프트 템플릿 + 수집된 뉴스·재무·공시를 하나의 md로 패킹)
  - **토큰 예산 적용** (`tiktoken` cl100k_base): 재무요약 500·공시 3건×300·뉴스 5건×200·프롬프트 템플릿 2,000 = 총 ~2,500 토큰. 초과 시 오래된 항목부터 `[truncated]` 마킹. MAX_CONTEXT_TOKENS는 `settings` 테이블에서 fetch
- **테스트 (Phase 4에 추가)**:
  - `test_enqueue.py`: 점수 65 이상/이하, 골든 시그널 유무 → 큐 추가 여부 4가지 케이스 확인
  - `test_enqueue.py`: 토큰 초과 입력 → 번들에 `[truncated]` 포함 + 총 토큰 ≤ MAX 확인
- 웹 UI `/queue` 페이지: 각 큐 아이템에 [다운로드] [프롬프트 복사] [결과 붙여넣기] 버튼
- 결과 업로드 시: `analysis_results/{ticker}_{prompt_type}_{run_id}.json` 파싱 → `agent_scores` 테이블 업데이트

### Phase 5 — Next.js 대시보드 UI (3주)
파일: `apps/web/app/`

**/dashboard** (홈)
- 시장 게이트 상태(KOSPI·S&P500 MA200 상회 여부)
- 신규 골든 시그널 (최근 7일) 피드
- 워치리스트 green/yellow 요약 카드
- 정량 점수 상위 30 테이블 (정렬·필터 가능)

**/stocks/[ticker]** (리포트 7부 템플릿 그대로 렌더)
- 한 줄 요약 + 점수 카드 (8 카테고리 + Claude 정성 3종)
- Recharts로 주가·거래량·외국인 지분 차트
- 트리거 이벤트 타임라인 (수직 스크롤, 공시 원문 링크)
- 리스크 3대 요인 (에이전트 결과)
- 모니터링 지표 위젯
- 유지·경고·매도 신호 상태 배지

**/signals** (골든 시그널 모음)
- 필터: 섹터·시장·트리거 유형·신뢰도
- 리포트 2-D 8선과 구조적 유사도 퍼센트

**/queue** (에이전트 인박스)
- 미처리 큐 리스트 + 프롬프트 다운로드 버튼
- 결과 업로드 폼 (JSON 검증 후 저장)
- 처리 이력

**/watchlist**
- green/yellow 카드 뷰
- 포지션 사이징 메모·손절·목표가
- yellow→green 전환 시 Telegram 알림 설정

**/settings** (사용자 요청 핵심)
- **업데이트 체크리스트**: 파이프라인 각 단계(유니버스/가격/재무/공시/뉴스/점수/큐/알림)별 마지막 실행 시각 + 성공/실패 + 수동 재실행 버튼
- **스케줄 설정**: 각 수집기의 cron 표현식 편집 (설정 저장 시 GitHub Actions `workflow_dispatch` + cron 주석 업데이트 PR 자동 생성)
- **필터 임계값**: 리포트 3-B/3-C의 각 필터 값을 UI에서 조정 (저장 시 `settings` 테이블 업데이트 → 다음 점수 계산에 즉시 반영)
- **가중치 조정**: 리포트 6-B 8 카테고리 가중치 슬라이더 + 몬테카를로 섭동 ±5%p 토글
- **알림 채널**: Telegram 봇 토큰·채팅ID·알림 조건 (yellow→green, 골든 시그널, 스코어 급등)
- **유니버스 관리**: 수동 티커 추가/제외, 상폐 종목 아카이브
- **실패 사례 학습**: `failure_cases` 테이블 CRUD UI — 에코프로·Beyond Meat·헬릭스미스 등 교훈 누적

### Phase 6 — 알림 & 스케줄러 (1주)
- Telegram Bot 연동 (`apps/web/lib/notify.ts`) — **토큰은 Cloudflare env var `TELEGRAM_BOT_TOKEN`**
- **파이프라인 실패 알림**: `pipeline_runs.status='error'`가 연속 2회 시 Telegram 알림 (`notify.ts`에 `alertPipelineFailure()` 추가)
- **데이터 신선도 배지**: 대시보드 상단에 "마지막 수집: N분 전" 배지 (pipeline_runs 최신 행 기준)
- GitHub Actions 워크플로우:
  - `collect-daily.yml`: 매일 06:00 KST (UTC 21:00) 재무·점수·큐 + `pipeline_runs` 기록
  - `collect-hourly.yml`: 매시간 공시·뉴스·가격 + `pipeline_runs` 기록
  - `collect-weekly.yml`: 일요일 22:00 KST 백테스트 → (완료 후) **가격 데이터 pruning** (`prune_prices.py`: DELETE WHERE date < NOW() - INTERVAL '2 years') — **순차 실행 필수** (병렬 시 백테스트가 pruning 대상 데이터 조회 중 삭제될 수 있음)
- Supabase pg_cron:
  - `CLAIMED` 큐 만료 복귀: 매 30분 실행 (`UPDATE analysis_queue SET status='PENDING' WHERE status='CLAIMED' AND claimed_at < NOW() - INTERVAL '48 hours'`)

### Phase 7 — 백테스트 & 검증 (1주)
- 2020-01-01 시점으로 되돌려 25+30=55종목 중 몇 개가 필터 통과하는지 측정 (리포트 2부 7-1 재현)
- point-in-time 유니버스 (상폐 포함) 구성
- 통과 종목 중 실제 10배 달성률 = 적중률 산출
- 몬테카를로 가중치 섭동으로 오버피팅 진단

### Phase 8 — 문서·배포·폴리싱 (1주)
- README (설치·Supabase 셋업·Cloudflare 연결·GitHub secret 목록)
- `.env.example`
- Cloudflare Access (단일 사용자 이메일 화이트리스트) 선택 가이드
- 에이전트 연동 가이드 (`docs/agent-workflow.md`): Claude Code로 큐 처리하는 표준 루프

## 재사용 가능한 외부 라이브러리

**Python (apps/collector):**
- **`OpenDartReader`** — DART OpenAPI 래퍼, 리포트 5-A 공식 권장
- **`FinanceDataReader`** — KR 가격·종목 데이터 (상폐주 포함)
- **`yfinance`** — US 가격 (비공식 API — Alpha Vantage Free 폴백 유지)
- **`pandas-ta>=0.3`** — RS·MA·거래량 기술적 지표 계산
- **`edgartools`** — SEC EDGAR 직접 파싱 (XBRL 재무 + 8-K 공시, 무료 오픈소스, `set_identity()` 필수)
- **`feedparser`** — 한경·조선비즈 RSS
- **`supabase-py`** — Supabase Python SDK
- **`pydantic>=2`** — agent 결과 JSON 스키마 검증
- **`tiktoken`** — 에이전트 번들 토큰 예산 계산
- **`pytest`** — 테스트 프레임워크

**TypeScript (apps/web):**
- **`@cloudflare/next-on-pages`** + **`wrangler`** — Cloudflare 배포 어댑터 (Phase 0 필수)
- **`@supabase/supabase-js`** — Supabase JS SDK
- **`@supabase/ssr`** — Cloudflare edge runtime용 Supabase 클라이언트 (`createClient` + `{ auth: { persistSession: false } }`)
- **`shadcn/ui`** + **`Tremor`** — 대시보드 컴포넌트
- **`Recharts`** — 차트 (일봉·수주잔고)
- **`TanStack Table v8`** — 정렬·필터 가능한 스크리닝 결과 테이블
- **`vitest`** + **React Testing Library** — 프론트엔드 테스트

## 주요 위험 & 완화

| 위험 | 완화 |
|---|---|
| DART OpenAPI 일 20,000건 제한 | 종목별 하루 1회 요청, 재무만 분기별로 갱신 |
| SEC EDGAR rate limit (10 req/sec, UA 필수) | `User-Agent` 헤더에 이메일 포함, 배치 간 sleep |
| yfinance 비공식 API 중단 위험 | 2차 소스로 Alpha Vantage Free 폴백 |
| Cloudflare Pages Functions 10ms CPU 한계 | 무거운 계산은 GitHub Actions에서 선계산 후 DB에 저장 |
| Supabase 무료 500MB 한계 | 일봉 데이터는 2년치만 유지, 오래된 건 파케이로 내보내 S3/R2 |
| 생존편향·과적합 | Phase 7 백테스트 필수 + `failure_cases` DB 누적 |
| 에이전트 파일 인박스 병목 | `/queue` UI에 배치 다운로드(zip) + 배치 결과 업로드 지원 |

## UI/UX 설계 명세

### 디자인 시스템 토큰

**테마:** 다크 모드 기본값 (Bloomberg/Robinhood 스타일)

```css
--color-bg:       #0f1117
--color-surface:  #1c1f26
--color-card:     #242836
--color-border:   #2d3147
--color-text-1:   #e8eaf0
--color-text-2:   #8890a4
--color-accent:   #3b82f6
--color-success:  #22c55e
--color-warning:  #f59e0b
--color-error:    #ef4444
--color-gold:     #f59e0b
```

**AI 슬롭 금지 항목:**
- ❌ 보라/인디고 그라데이션 배경
- ❌ 아이콘-원형-컬러 3열 feature grid
- ❌ 모든 요소 동일 border-radius (카드 8px, 버튼 6px, 뱃지 4px)
- ❌ emoji를 디자인 요소로 사용
- ❌ centered text-align 남발

### 인터랙션 상태 매트릭스

| 페이지/컴포넌트 | Loading | Empty | Error | Success |
|---|---|---|---|---|
| **Dashboard 전체** | 섹션별 skeleton | "아직 수집된 데이터가 없습니다. [지금 수집 실행]" | "데이터베이스 연결 실패" + 재시도 배너 | 정상 표시 |
| **골든 시그널 피드** | 3개 skeleton 카드 | "이번 주 골든 시그널 없음" | 인라인 "불러오기 실패 [재시도]" | 정상 카드 |
| **스코어 테이블** | TanStack 로딩 오버레이 | "스크리닝 결과 없음" | error card | 정상 |
| **/stocks/[ticker]** | 차트 skeleton pulse | 에이전트 점수 미존재 → "분석 큐에 추가하기" | "가격 데이터 없음" | 정상 |
| **/queue** | 리스트 skeleton | "분석 큐가 비어있습니다" | error banner | 정상 |
| **/settings 저장** | 버튼 loading spinner | — | DB/GitHub API 오류 별도 표시 | "저장됨 ✓" toast |

### 5개 핵심 설계 결정

**결정 1 — 데이터 신선도 정책:**
- 스코어 테이블: staleTime=30분, 수동 새로고침 버튼
- 시그널 피드: staleTime=1분 (자동 background refetch)
- 마지막 수집 배지: staleTime=10초

**결정 2 — 골든 시그널 카드:** golden=true 이벤트 최근 7일, 최대 3개 inline, [전체 N개 보기] 링크

**결정 3 — [+워치리스트] 버튼:** 클릭 → 3-field modal (목표가·손절·메모) → status='candidate' 추가

**결정 4 — 큐 항목 타임아웃:** CLAIMED 38h+ → ⚠️ 배지 / pg_cron 48h 후 자동 PENDING 복귀 / [강제 리셋] 버튼

**결정 5 — 설정 크론 편집:** settings 저장 → GitHub API workflow 파일 업데이트 시도 → [지금 실행] workflow_dispatch

## 리뷰 결정사항 요약

### CEO 리뷰 (2026-04-23)
| # | 이슈 | 결정 |
|---|---|---|
| 1 | pipeline_runs 테이블 없음 | Supabase `pipeline_runs` 테이블 추가 |
| 2 | Cloudflare Pages 어댑터 미정의 | `@cloudflare/next-on-pages` Phase 0에 명시 |
| 3 | GitHub Actions 무료 분 초과 | Public repo로 고정 |
| 4 | Python이 settings 변경 인식 불가 | startup 시 Supabase에서 fetch (`settings_loader.py`) |
| 5 | 테스트 계획 없음 | Phase 2에 pytest 테스트 통합 |

### 엔지니어링 리뷰 (2026-04-23)
| # | 이슈 | 결정 |
|---|---|---|
| 1 | `@supabase/supabase-js` edge runtime 오류 | `@supabase/ssr` + `{ auth: { persistSession: false } }` |
| 2 | `sec-api.io` 유료 ($49/월~) | `edgartools` 오픈소스로 대체 |
| 3 | 에이전트 번들 토큰 무제한 | `tiktoken` 섹션별 토큰 예산 적용 (~2,500 토큰) |

### 구현 완료 현황 (2026-04-26)
- ✅ Phase 0 — 저장소 부트스트랩
- ✅ Phase 1 — 데이터 파이프라인
- ✅ Phase 2 — 정량 스크리닝 엔진 + 테스트 (110/110 통과)
- ✅ Phase 3 — 트리거 이벤트 탐지
- ✅ Phase 4 — 에이전트 큐
- ✅ Phase 5 — Next.js 대시보드 UI (진행 중)
- ✅ Cloudflare Pages 빌드 성공 (deployment `ace2579a`)
- ✅ GitHub Actions Hourly/Daily 정상 동작
