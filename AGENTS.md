# StockResearch — AGENTS.md

## 프로젝트 개요

10배 상승주 조기 발굴 시스템. KOSPI/KOSDAQ/S&P1500 유니버스에서 정량 스크리닝 + 정성 분석 에이전트를 조합해 후보 종목을 추려내는 단일 사용자 대시보드.

**배포 아키텍처**
- `apps/web/` → Cloudflare Pages (Next.js 14, edge runtime)
- `apps/collector/` → GitHub Actions 크론 (Python 데이터 수집)
- Supabase Postgres (DB + Storage)

---

## 현재 진행 상태 (2026-04-25 기준)

### 완료된 Phase
- **Phase 0** — 저장소 부트스트랩 완료 (모노레포, Supabase 마이그레이션, GitHub Actions)
- **Phase 1** — Python 데이터 파이프라인 완료 (universe/prices/financials/filings/news)
- **Phase 2** — 정량 스크리닝 엔진 완료 (filters_kr/us, score, backtest)
- **Phase 3** — 트리거 이벤트 탐지 완료 (classifier, golden_signal)
- **Phase 4** — 에이전트 큐 완료 (enqueue, 토큰 예산)
- **Python 테스트** — 110/110 통과
- **Cloudflare Pages 빌드** — ✅ 성공 (deployment `ace2579a`, commit `6a0c33c`)
- **GitHub Actions** — ✅ Hourly/Daily 워크플로우 정상 동작 확인

### 미완료 설정 (수동 진행 필요)
- CF API 토큰 생성 및 적용 (아래 상세 가이드 참고)

---

## Cloudflare Pages 빌드 — 핵심 설정 및 히스토리

### 문제 해결 이력

**문제 1: wrangler.toml 위치**
- CF Pages는 **repo root**의 `wrangler.toml`을 읽는다
- `pages_build_output_dir`은 repo root 기준 상대경로
- 현재 root `wrangler.toml`: `pages_build_output_dir = "apps/web/.vercel/output/static"`
- `apps/web/wrangler.toml`도 공존 (CF Pages가 `apps/web/`에서 실행할 때 사용): `pages_build_output_dir = ".vercel/output/static"`

**문제 2: export const runtime = 'edge' 누락**
- `@cloudflare/next-on-pages` v1.x는 **모든 server-rendered 라우트**에 edge runtime 선언 필수
- 현재 적용 완료: `layout.tsx`, `(dashboard)/page.tsx`, `queue/page.tsx`, `settings/page.tsx`, `signals/page.tsx`, `watchlist/page.tsx`, `stocks/[ticker]/page.tsx`
- `'use client'` 페이지는 `'use client'` 바로 다음 줄에 `export const runtime = 'edge'` 추가

**문제 3: pip install . 실패 — setuptools 패키지 자동 발견**
- CF Pages는 `pyproject.toml` 감지 시 `pip install .` 자동 실행
- `apps/`, `packages/`, `node_modules/` 디렉토리를 패키지로 오인
- 해결: root `pyproject.toml`에 `[tool.setuptools] packages = []` 추가

**문제 4: pip install . 실패 — FinanceDataReader Python 3.13 미지원**
- CF Pages 환경: Python 3.13.3
- `FinanceDataReader`는 Python 3.13에서 설치 불가
- 해결: root `pyproject.toml`의 `dependencies = []` (빈 배열), 모든 Python 의존성을 `apps/collector/pyproject.toml`로 이동

**문제 5: build 스크립트 무한 루프 (✅ 해결 — commit `6a0c33c`)**
- CF Pages 빌드 커맨드: `cd apps/web && pnpm install && pnpm build`
- `pnpm build` = `npx @cloudflare/next-on-pages` → 내부에서 `vercel build` 호출 → `pnpm run build` 재호출 → 무한 루프
- 해결: `VERCEL=1` 환경변수 체크로 분기
  ```json
  "build": "node -e \"const{execSync:e}=require('child_process');e(process.env.VERCEL?'next build':'npx @cloudflare/next-on-pages',{stdio:'inherit'})\""
  ```
- `VERCEL=1`인 경우 (vercel build 내부): `next build`만 실행
- `VERCEL` 없는 경우 (CF Pages 진입점): `@cloudflare/next-on-pages` 전체 실행
- **배포 결과**: `https://ace2579a.stockresearch-7kh.pages.dev` ✅

### 현재 파일 상태

```
wrangler.toml (repo root)
  pages_build_output_dir = "apps/web/.vercel/output/static"
  compatibility_flags = ["nodejs_compat"]

apps/web/wrangler.toml
  pages_build_output_dir = ".vercel/output/static"

apps/web/package.json
  "build": "node -e \"...VERCEL ? 'next build' : 'npx @cloudflare/next-on-pages'...\""  ← 무한루프 방지
  "pages:build": "npx @cloudflare/next-on-pages"

pyproject.toml (repo root)
  dependencies = []
  [tool.setuptools] packages = []

apps/collector/pyproject.toml
  모든 Python 의존성 포함
```

### CF Pages 대시보드 설정
- **빌드 커맨드**: `cd apps/web && pnpm install && pnpm build`
- **루트 디렉토리**: (비어있음 — repo root)
- **출력 디렉토리**: `apps/web/.vercel/output/static` (wrangler.toml로 자동 설정됨)

---

## Cloudflare API 토큰 설정 가이드

### 왜 필요한가?
`/api/deployments` 라우트가 CF Pages 최신 배포 상태를 조회한다. 설정 페이지에서 "마지막 CF Pages 배포: N분 전" 같은 정보를 보여줄 수 있다.

### 1. 토큰 생성 (dash.cloudflare.com)

1. `https://dash.cloudflare.com/profile/api-tokens` 접속
2. **Create Token** 클릭
3. **"Cloudflare Pages" 템플릿** 선택 (또는 Custom Token으로 아래 권한만 설정)
   - 최소 권한: `Account → Cloudflare Pages → Read`
4. Account Resources: `Include → All accounts` (또는 특정 계정)
5. **Continue to Summary** → **Create Token**
6. 토큰 값 복사 (한 번만 표시됨)

### 2. 토큰 저장 — Cloudflare Pages 환경변수 (웹 앱용)

1. `https://dash.cloudflare.com/244c48047ff6f631154391563e48daac/pages/view/stockresearch/settings/environment-variables` 접속
2. **Production** 환경에 아래 변수 추가:

| 변수명 | 값 | 설명 |
|---|---|---|
| `CF_API_TOKEN` | `<토큰 값>` | 위에서 생성한 토큰 |
| `CF_ACCOUNT_ID` | `244c48047ff6f631154391563e48daac` | URL에서 확인한 계정 ID |
| `CF_PROJECT_NAME` | `stockresearch` | CF Pages 프로젝트명 |

3. **Save** 후 새 배포 트리거 (main 푸시 또는 CF 대시보드에서 Retry deployment)

### 3. Account ID 확인
- CF 대시보드 URL: `https://dash.cloudflare.com/244c48047ff6f631154391563e48daac/...`
- 위 URL에서 `244c48047ff6f631154391563e48daac`가 Account ID

### 4. 기존 "GitHub Actions" 토큰
CF 대시보드에 이미 `GitHub Actions` 토큰 (Account.Cloudflare Pages 권한)이 존재한다. 이 토큰 값을 알고 있다면 새로 생성 없이 재사용 가능. 토큰 값을 모른다면 위 절차대로 신규 생성.

### 5. 사용처
- `apps/web/app/api/deployments/route.ts` — CF Pages 최신 5개 배포 목록 반환
- 응답 형식: `{ deployments: [{ id, url, created_on, status, stage, environment, commit_message, commit_hash }] }`

---

## 미완료 설정 항목

| 항목 | 상태 | 위치 |
|---|---|---|
| CF API 토큰 | ✅ **적용 완료** | CF Pages Secret `CF_API_TOKEN` 저장됨, wrangler.toml에 `CF_ACCOUNT_ID` / `CF_PROJECT_NAME` 추가 |
| DART API Key | 미설정 | GitHub Secret `DART_API_KEY` |
| Telegram Bot Token | 미설정 | Cloudflare env var `TELEGRAM_BOT_TOKEN` |
| Telegram Chat ID | 미설정 | Cloudflare env var `TELEGRAM_CHAT_ID` |
| GitHub PAT | ✅ **적용 완료** | CF Pages Secret `GITHUB_PAT` 저장됨 (OAuth token, workflow scope), GitHub Secret은 별도 |
| GitHub Repo | ✅ **적용 완료** | `apps/web/wrangler.toml` `[vars]` `GITHUB_REPO = "nty203/StockResearch"` |
| Supabase Storage bucket | 미생성 | `analysis-prompts` 버킷 생성 필요 |
| Supabase DB 마이그레이션 | 완료 여부 확인 필요 | `supabase/migrations/001_init.sql` |

### GitHub Actions Secrets (현재 설정됨)
- `SUPABASE_URL` ✅
- `SUPABASE_SERVICE_KEY` ✅
- `SUPABASE_DB_URL` ✅
- `DART_API_KEY` — 실제 값 확인 필요

### Cloudflare Pages 환경변수 (현재 설정됨)
- `SUPABASE_URL` ✅
- `SUPABASE_SERVICE_KEY` ✅
- `NEXT_PUBLIC_SUPABASE_URL` ✅
- `NEXT_PUBLIC_SUPABASE_ANON_KEY` ✅

---

## GitHub Actions Diagnostic Workflow

`.github/workflows/cf-build-test.yml` — 빌드 디버깅용으로 생성됨. 더 이상 필요 없으므로 삭제 가능.

---

## 중요 기술 규칙

### Next.js / Cloudflare
- 모든 route handler (`app/api/**/route.ts`)에 `export const runtime = 'edge'` 필수
- 모든 page 파일에 `export const runtime = 'edge'` 필수
- `'use client'` 파일에서는 `'use client'` 다음 줄에 위치
- Supabase 클라이언트: `@supabase/ssr` + `{ auth: { persistSession: false } }` (edge 호환)
- Node.js 전용 API 절대 사용 금지 (edge runtime 제한)
- App shell: `layout.tsx`(Server) → `<AppShell>`(client, drawer state) → `<Sidebar>` + `<Header>` + `<main>`. 모바일(`<md`)에서는 사이드바가 햄버거 drawer, 데스크톱(`>=md`)에서는 항상 표시.

### Python / GitHub Actions
- Supabase 연결: pooler URL 사용 (`project.pooler.supabase.com:6543`) — free tier 직접 연결 5개 제한
- 모든 `src/` 하위 패키지 디렉토리에 `__init__.py` 필요
- 설정값은 하드코딩 금지 — `settings_loader.py`로 Supabase `settings` 테이블에서 fetch
- `edgartools` 사용 시 `set_identity('name email')` 필수, rate limit 0.1초 sleep 삽입

### GitHub Actions
- 모든 workflow yml에 `workflow_dispatch:` 트리거 필수 (/settings 수동 재실행 버튼이 사용)
- `collect-weekly.yml`: 백테스트 → prune_prices 순서 고정 (병렬 실행 금지)

---

## 파일 구조 요약

```
StockResearch/                         ← 100배 종목 분석/발굴 전용 시스템
├── AGENTS.md
├── wrangler.toml                      ← CF Pages root config
├── pyproject.toml                     ← 빈 workspace coordinator
├── package.json                       ← pnpm workspace root
├── pnpm-workspace.yaml
├── apps/
│   ├── web/                           ← Next.js (Cloudflare Pages)
│   │   ├── wrangler.toml
│   │   └── app/
│   │       ├── layout.tsx             ← edge runtime
│   │       ├── page.tsx               ← / (100배 시그널 메인, /hundredx alias)
│   │       ├── hundredx/page.tsx      ← /hundredx (alias) — / 와 동일 콘텐츠
│   │       ├── library/page.tsx       ← /library (historical 100배 라이브러리)
│   │       └── api/
│   │           └── hundredx/
│   │               ├── route.ts          ← 매치 종목 목록 (conviction 정렬)
│   │               ├── [ticker]/route.ts ← 단일 종목 매치 상세
│   │               └── library/route.ts  ← 라이브러리 종목 목록
│   └── collector/                     ← Python 데이터 수집/분석
│       ├── pyproject.toml             ← 모든 Python 의존성
│       └── src/
│           ├── universe.py            ← 종목 메타데이터
│           ├── prices.py              ← 가격 (FDR + yfinance)
│           ├── financials_dart.py     ← 재무 (DART)
│           ├── financials_sec.py      ← 재무 (SEC)
│           ├── filings_watch.py       ← 공시 수집
│           ├── news_rss.py            ← 뉴스 수집
│           ├── upsert.py              ← Supabase 공유 유틸
│           ├── utils/
│           │   ├── db_fetch.py        ← bulk_fetch_financials (hundredx 사용)
│           │   ├── settings.py        ← settings 테이블 loader
│           │   └── prune_prices.py    ← 2년 초과 가격 prune
│           └── hundredx/              ← 100배 분석 엔진 (코어)
│               ├── models.py          ← CategoryMatch dataclass
│               ├── keywords.py        ← 카테고리별 키워드 lib
│               ├── scanner.py         ← 메인 orchestrator (daily)
│               ├── discover.py        ← 5y 가격에서 100배+ 자동 발견
│               ├── extract_signals.py ← 시그널 자동 추출 + 카테고리 분류
│               ├── backfill_history.py ← DART historical 공시 백필
│               ├── update_library.py  ← 주간 latest_multiplier 갱신
│               ├── auto_populate.py   ← discover+backfill+extract orchestrator
│               ├── fingerprint_match.py ← 라이브러리 fingerprint 매칭
│               ├── timeline_match.py  ← trigger sequence timeline 매칭
│               └── categories/        ← 7개 카테고리 디텍터
│                   ├── backlog_lead.py
│                   ├── bigtech_partner.py
│                   ├── clinical_pipe.py
│                   ├── platform_mono.py
│                   ├── policy_benefit.py
│                   ├── profit_inflect.py
│                   └── supply_choke.py
├── packages/shared/                   ← TypeScript 공유 타입 (hundredx 전용으로 슬림화)
├── supabase/migrations/               ← DB 스키마
└── .github/workflows/                 ← GitHub Actions (5개)
    ├── collect-hourly.yml             ← 매시간: filings + news
    ├── collect-daily.yml              ← 매일 06:00 KST: universe + prices
    ├── collect-hundredx.yml           ← 매일 06:00 KST: 100배 scanner
    ├── collect-weekly.yml             ← 일요일 22:00 KST: financials + library 갱신
    └── hundredx-auto-populate.yml     ← 매월 1일 03:00 KST: 자동 발견 + 시그널 추출
```

---

## 다음 작업 순서

1. ✅ **CF API 토큰 생성 완료** — `StockResearch Full Access` (Cloudflare Pages:Edit, Account Settings:Read), CF Pages Secret `CF_API_TOKEN` 저장, wrangler.toml에 `CF_ACCOUNT_ID`/`CF_PROJECT_NAME` 추가
2. ✅ **GitHub PAT 설정 완료** — GitHub OAuth token (workflow scope), CF Pages Secret `GITHUB_PAT` 저장 (wrangler pages secret put), wrangler.toml에 `GITHUB_REPO = "nty203/StockResearch"` 추가. 트리거 버튼 피드백 UI도 추가 (commit `934cb42`)
3. **[수동]** `.github/workflows/cf-build-test.yml` 삭제 (빌드 성공 후 필요 없음)
4. **[수동]** Supabase Storage `analysis-prompts` 버킷 생성
5. **[수동]** DART API Key 실제 값 설정, Telegram 설정 완료
6. Phase 5 Next.js 대시보드 UI 폴리싱 (계속)
7. Phase 6-8 (알림, 백테스트, 문서)

---

## PPTR 품질 게이트 및 커버리지 규칙 (2026-05-23)

다음 작업자/AI는 PPTR A급 조건을 임의로 완화하지 말 것.

- 검증 범위: 국내 활성 KOSPI/KOSDAQ 2,776개, 활성 PPTR 룰 17개
- 검증 결과: A급 PPTR 완전 매칭 0개
- 해석: 현재 수집된 DB 데이터 기준으로 과거 100x 샘플 룰을 완전 충족하는 국내 종목이 없다는 뜻
- 금지: 후보를 만들기 위해 키워드 수, 섹터, BCR/OPM/금액 조건을 임의로 낮추는 것
- 금지: `미분류`, `단기_테마_급등`, 거래량 스파이크 단독 룰을 성장 후보로 사용하는 것
- 금지: 라이브러리 종목이 자기 자신의 PPTR 룰에 매칭되는 것
- near-miss도 키워드/금액/BCR 같은 특이 신호가 하나 이상 있어야 하며, 섹터+OPM만으로 저장하지 말 것
- B/C급 후보는 A급과 별도 등급/테이블/화면으로 분리할 것

주의: 전체 PPTR 스캔은 실시간 웹 크롤링이 아니라 Supabase에 이미 수집된 filings/news/financials/prices 기반이다. 뉴스/공시 수집이 누락되면 PPTR도 누락된다. "A급 없음"을 말하기 전에는 `apps/collector/src/hundredx/data_coverage.py` 또는 동등한 점검으로 filings/news freshness와 raw_text coverage를 확인할 것.

세부 기준과 누락 가능성은 `docs/pptr-quality-and-coverage.md` 참조.
