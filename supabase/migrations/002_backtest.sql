-- ============================================================
-- 백테스트 결과 테이블 (002)
-- ============================================================

CREATE TABLE backtest_runs (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  run_date    DATE NOT NULL DEFAULT CURRENT_DATE,
  triggered_by TEXT,           -- 'github_actions' | 'ui' | 'manual'
  dart_used   BOOLEAN NOT NULL DEFAULT false,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE backtest_results (
  id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  run_id        UUID NOT NULL REFERENCES backtest_runs(id) ON DELETE CASCADE,
  ticker        TEXT NOT NULL,
  name          TEXT,
  market        TEXT,
  snapshot_date DATE NOT NULL,
  peak_date     DATE,
  actual_x      NUMERIC,       -- 실제 수익률 배수 (예: 107.0 = 107배)
  score_10x     NUMERIC,       -- 10X 점수 (0~100)
  passed        BOOLEAN NOT NULL DEFAULT false,
  failed_filters TEXT[],       -- 필터 탈락 목록
  cats          JSONB,         -- 카테고리별 점수 {growth, momentum, quality, ...}
  price_at_snapshot NUMERIC,
  rs_score      NUMERIC,
  is_target     BOOLEAN NOT NULL DEFAULT false,  -- true=타겟, false=대조군
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ON backtest_results(run_id);
CREATE INDEX ON backtest_runs(run_date DESC);
