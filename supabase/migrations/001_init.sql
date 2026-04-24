-- ============================================================
-- 10배 스크리너 초기 스키마
-- Apply: npx supabase db push
-- Rollback: supabase/migrations/001_rollback.sql
-- ============================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_cron;

-- ── 유니버스 & 종목 메타 ──────────────────────────────────────
CREATE TABLE stocks (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  ticker      TEXT NOT NULL,
  market      TEXT NOT NULL CHECK (market IN ('KOSPI','KOSDAQ','NYSE','NASDAQ')),
  name_kr     TEXT,
  name_en     TEXT,
  sector_wics TEXT,
  industry    TEXT,
  is_active   BOOLEAN NOT NULL DEFAULT true,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (ticker, market)
);

-- ── 일봉 시세 (2년치 유지) ────────────────────────────────────
CREATE TABLE prices_daily (
  ticker     TEXT NOT NULL,
  date       DATE NOT NULL,
  open       NUMERIC,
  high       NUMERIC,
  low        NUMERIC,
  close      NUMERIC NOT NULL,
  volume     BIGINT,
  adj_close  NUMERIC,
  PRIMARY KEY (ticker, date)
);
CREATE UNIQUE INDEX ON prices_daily(ticker, date);

-- ── 분기 재무 ─────────────────────────────────────────────────
-- fq 형식: 'YYYYQ[1-4]' (예: '2023Q1') — DART·SEC 공통 정규화
CREATE TABLE financials_q (
  id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  ticker            TEXT NOT NULL,
  fq                TEXT NOT NULL,   -- e.g. '2023Q1'
  revenue           NUMERIC,
  op_income         NUMERIC,
  net_income        NUMERIC,
  op_margin         NUMERIC,         -- 0~1 비율
  roe               NUMERIC,
  roic              NUMERIC,
  fcf               NUMERIC,
  debt_ratio        NUMERIC,
  interest_coverage NUMERIC,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX ON financials_q(ticker, fq);

-- ── 수주·주요 공시 ────────────────────────────────────────────
CREATE TABLE filings (
  id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  ticker           TEXT NOT NULL,
  source           TEXT NOT NULL CHECK (source IN ('DART','SEC')),
  filing_type      TEXT NOT NULL,
  filed_at         TIMESTAMPTZ NOT NULL,
  url              TEXT NOT NULL,
  headline         TEXT NOT NULL,
  raw_text         TEXT,
  keywords         TEXT[] NOT NULL DEFAULT '{}',
  parsed_amount    NUMERIC,
  parsed_customer  TEXT,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ON filings(ticker, filed_at DESC);

-- ── 뉴스 (RSS) ───────────────────────────────────────────────
CREATE TABLE news (
  id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  ticker       TEXT NOT NULL,
  source       TEXT NOT NULL,
  published_at TIMESTAMPTZ NOT NULL,
  url          TEXT NOT NULL UNIQUE,
  title        TEXT NOT NULL,
  summary      TEXT,
  lang         TEXT NOT NULL CHECK (lang IN ('ko','en'))
);
CREATE INDEX ON news(ticker, published_at DESC);

-- ── 정량 점수 (매일 전체 재계산) ──────────────────────────────
CREATE TABLE screen_scores (
  ticker          TEXT NOT NULL,
  run_date        DATE NOT NULL,
  growth          NUMERIC NOT NULL DEFAULT 0,
  momentum        NUMERIC NOT NULL DEFAULT 0,
  quality         NUMERIC NOT NULL DEFAULT 0,
  sponsorship     NUMERIC NOT NULL DEFAULT 0,
  value           NUMERIC NOT NULL DEFAULT 0,
  safety          NUMERIC NOT NULL DEFAULT 0,
  size            NUMERIC NOT NULL DEFAULT 0,
  market_gate     NUMERIC NOT NULL DEFAULT 1,
  score_10x       NUMERIC NOT NULL DEFAULT 0,
  percentile      NUMERIC NOT NULL DEFAULT 0,  -- 0~100
  passed          BOOLEAN NOT NULL DEFAULT false,
  failed_filters  TEXT[] NOT NULL DEFAULT '{}',
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (ticker, run_date)
);
CREATE UNIQUE INDEX ON screen_scores(ticker, run_date);

-- ── 에이전트 정성 점수 ────────────────────────────────────────
CREATE TABLE agent_scores (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  ticker          TEXT NOT NULL,
  run_date        DATE NOT NULL,
  prompt_type     TEXT NOT NULL,
  demand_score    NUMERIC,    -- 0~10
  moat_score      NUMERIC,
  trigger_score   NUMERIC,
  narrative_md    TEXT,
  risks_md        TEXT,
  bull_bear_ratio NUMERIC,
  agent_model     TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX ON agent_scores(ticker, run_date, prompt_type);

-- ── 트리거 이벤트 ─────────────────────────────────────────────
CREATE TABLE trigger_events (
  id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  ticker           TEXT NOT NULL,
  event_type       TEXT NOT NULL,
  detected_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  confidence       NUMERIC NOT NULL DEFAULT 0,  -- 0~100
  source_filing_id UUID REFERENCES filings(id) ON DELETE SET NULL,
  matched_keywords TEXT[] NOT NULL DEFAULT '{}',
  summary          TEXT NOT NULL,
  golden           BOOLEAN NOT NULL DEFAULT false
);
CREATE INDEX ON trigger_events(ticker, detected_at DESC);
CREATE INDEX ON trigger_events(golden, detected_at DESC);

-- ── 워치리스트 ───────────────────────────────────────────────
CREATE TABLE watchlist (
  id                 UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  ticker             TEXT NOT NULL,
  status             TEXT NOT NULL DEFAULT 'candidate'
                     CHECK (status IN ('candidate','yellow','green')),
  added_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  notes              TEXT,
  target_price       NUMERIC,
  stop_loss          NUMERIC,
  position_size_plan TEXT
);

-- ── 분석 큐 ──────────────────────────────────────────────────
CREATE TABLE analysis_queue (
  id                   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  ticker               TEXT NOT NULL,
  prompt_type          TEXT NOT NULL,
  status               TEXT NOT NULL DEFAULT 'PENDING'
                       CHECK (status IN ('PENDING','CLAIMED','COMPLETED','FAILED','INVALID')),
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  claimed_at           TIMESTAMPTZ,
  storage_path_prompt  TEXT,
  storage_path_result  TEXT,
  claimed_by           TEXT
);
-- PENDING/CLAIMED 상태에서 동일 (ticker, prompt_type) 중복 방지
CREATE UNIQUE INDEX ON analysis_queue(ticker, prompt_type)
  WHERE status IN ('PENDING','CLAIMED');

-- ── 파이프라인 실행 로그 ──────────────────────────────────────
CREATE TABLE pipeline_runs (
  id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  stage          TEXT NOT NULL,
  started_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  ended_at       TIMESTAMPTZ,
  status         TEXT NOT NULL DEFAULT 'running'
                 CHECK (status IN ('running','success','error')),
  rows_processed INTEGER,
  error_msg      TEXT,
  github_run_id  TEXT
);
CREATE INDEX ON pipeline_runs(stage, started_at DESC);

-- ── 설정 ─────────────────────────────────────────────────────
CREATE TABLE settings (
  key        TEXT PRIMARY KEY,
  value_json JSONB NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 기본 설정값
INSERT INTO settings (key, value_json) VALUES
  ('enqueue_score_threshold',  '65'),
  ('max_bundle_tokens',        '15000'),
  ('market_gate_enabled',      'true'),
  ('score_weights', '{
    "growth": 28, "momentum": 22, "quality": 17,
    "sponsorship": 12, "value": 7, "safety": 7, "size": 7
  }'),
  ('kr_filters', '{}'),
  ('us_filters', '{}'),
  ('collect_daily_cron',  '"0 21 * * *"'),
  ('collect_hourly_cron', '"0 * * * *"');

-- ── 실패 사례 학습 DB ─────────────────────────────────────────
-- id PK: 한 종목이 여러 번 실패 가능
CREATE TABLE failure_cases (
  id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  ticker       TEXT NOT NULL,
  peak_at      DATE NOT NULL,
  peak_price   NUMERIC NOT NULL,
  trough_at    DATE NOT NULL,
  trough_price NUMERIC NOT NULL,
  early_signals TEXT[] NOT NULL DEFAULT '{}',
  lesson_md    TEXT
);

-- ── pg_cron: CLAIMED 큐 만료 복귀 (매 30분) ──────────────────
SELECT cron.schedule(
  'queue-timeout-reset',
  '*/30 * * * *',
  $$
  UPDATE analysis_queue
  SET status = 'PENDING', claimed_at = NULL, claimed_by = NULL
  WHERE status = 'CLAIMED'
    AND claimed_at < NOW() - INTERVAL '48 hours';

  INSERT INTO pipeline_runs (stage, ended_at, status, rows_processed)
  SELECT 'queue_reset', now(), 'success', COUNT(*)
  FROM analysis_queue
  WHERE status = 'PENDING'
    AND claimed_at IS NULL
    AND created_at > now() - INTERVAL '1 minute';
  $$
);
