# StockResearch — CLAUDE.md

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

### 진행 중 (최우선)
- **Cloudflare Pages 빌드 성공시키기**

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

**문제 5: build 스크립트가 next build 실행 (현재 최신 커밋 1cf3b7d에서 수정 중)**
- CF Pages 빌드 커맨드: `cd apps/web && pnpm install && pnpm build`
- `pnpm build` = `next build` → 출력이 `.next/`이고 `.vercel/output/static/`가 생성 안 됨
- 해결: `apps/web/package.json`의 `build` 스크립트를 `npx @cloudflare/next-on-pages`로 변경
- `@cloudflare/next-on-pages`는 내부적으로 `next build`를 실행하고 결과를 `.vercel/output/static/`으로 변환

### 현재 파일 상태

```
wrangler.toml (repo root)
  pages_build_output_dir = "apps/web/.vercel/output/static"
  compatibility_flags = ["nodejs_compat"]

apps/web/wrangler.toml
  pages_build_output_dir = ".vercel/output/static"

apps/web/package.json
  "build": "npx @cloudflare/next-on-pages"   ← 최신 수정
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

## GitHub Actions Diagnostic Workflow

`.github/workflows/cf-build-test.yml` — 빌드 디버깅용으로 생성됨. 빌드 성공 후 삭제 예정.

---

## 미완료 설정 항목

| 항목 | 상태 | 위치 |
|---|---|---|
| DART API Key | 미설정 | `apps/collector/.env` (placeholder) |
| Telegram Bot Token | 미설정 | Cloudflare env var `TELEGRAM_BOT_TOKEN` 필요 |
| Telegram Chat ID | 미설정 | Cloudflare env var `TELEGRAM_CHAT_ID` 필요 |
| Supabase Storage bucket | 미생성 | `analysis-prompts` 버킷 생성 필요 |
| Supabase DB 마이그레이션 | 완료 여부 확인 필요 | `supabase/migrations/001_init.sql` |

---

## 중요 기술 규칙

### Next.js / Cloudflare
- 모든 route handler (`app/api/**/route.ts`)에 `export const runtime = 'edge'` 필수
- 모든 page 파일에 `export const runtime = 'edge'` 필수
- `'use client'` 파일에서는 `'use client'` 다음 줄에 위치
- Supabase 클라이언트: `@supabase/ssr` + `{ auth: { persistSession: false } }` (edge 호환)
- Node.js 전용 API 절대 사용 금지 (edge runtime 제한)

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
StockResearch/
├── CLAUDE.md                          ← 이 파일
├── wrangler.toml                      ← CF Pages root config
├── pyproject.toml                     ← 빈 workspace coordinator
├── package.json                       ← pnpm workspace root
├── pnpm-workspace.yaml
├── apps/
│   ├── web/                           ← Next.js (Cloudflare Pages)
│   │   ├── wrangler.toml
│   │   ├── package.json               ← build: npx @cloudflare/next-on-pages
│   │   └── app/
│   │       ├── layout.tsx             ← export const runtime = 'edge' 있음
│   │       ├── (dashboard)/page.tsx   ← edge 있음
│   │       ├── queue/page.tsx         ← edge 있음
│   │       ├── settings/page.tsx      ← edge 있음
│   │       ├── signals/page.tsx       ← edge 있음
│   │       ├── watchlist/page.tsx     ← edge 있음
│   │       └── stocks/[ticker]/page.tsx ← edge 있음
│   └── collector/                     ← Python 데이터 수집
│       ├── pyproject.toml             ← 모든 Python 의존성
│       └── src/
│           ├── universe.py
│           ├── prices.py
│           ├── financials_dart.py
│           ├── financials_sec.py
│           ├── filings_watch.py
│           ├── news_rss.py
│           ├── upsert.py
│           ├── screening/
│           │   ├── filters_kr.py
│           │   ├── filters_us.py
│           │   ├── score.py
│           │   ├── peak_risk.py
│           │   ├── settings_loader.py
│           │   └── backtest.py
│           ├── triggers/
│           │   ├── classifier.py
│           │   └── golden_signal.py
│           └── queue/
│               └── enqueue.py
├── packages/shared/                   ← TypeScript 공유 타입
├── supabase/migrations/               ← DB 스키마
└── .github/workflows/                 ← GitHub Actions
    ├── collect-daily.yml
    ├── collect-hourly.yml
    ├── collect-weekly.yml
    └── cf-build-test.yml              ← 빌드 성공 후 삭제 예정
```

---

## 다음 작업 순서

1. **[진행 중]** Cloudflare Pages 빌드 성공 확인 (커밋 `1cf3b7d` 빌드 결과 확인)
2. 빌드 성공 후 `.github/workflows/cf-build-test.yml` 삭제
3. Supabase Storage `analysis-prompts` 버킷 생성
4. DART API Key, Telegram 설정 완료
5. Phase 5 Next.js 대시보드 UI 폴리싱
6. Phase 6-8 (알림, 백테스트, 문서)
