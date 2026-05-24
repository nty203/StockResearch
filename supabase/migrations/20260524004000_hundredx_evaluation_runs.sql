-- HundredX scanner / matching pipeline 평가 결과 저장 테이블.
-- 한 row = 한 번의 evaluation pipeline 실행 결과.
-- 시계열 비교 가능 (scanner 룰 변경 전후 효과 측정).

CREATE TABLE IF NOT EXISTS hundredx_evaluation_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    run_kind        TEXT NOT NULL DEFAULT 'full',  -- full | diagnostics | recall | calibration | forward_returns
    git_commit      TEXT,                           -- 재현용 — scanner 버전 트래킹
    params          JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- 평가 입력 요약 (어떤 데이터로 평가했나)
    n_matches_total     INT,
    n_matches_window    INT,         -- 평가 윈도우 안에 있던 match 수
    window_days         INT,
    n_library_stocks    INT,

    -- A. Diagnostics (current matches 기반)
    diagnostics         JSONB,
    -- {
    --   category_distribution: {cat: n},
    --   category_entropy: 0.59,
    --   body_coverage_pct: 36.0,
    --   sector_category_mismatch_rate: 0.0,
    --   library_overlap_rate: 0.60,
    --   llm_verdict_distribution: {confirm: 6, uncertain: 18, reject: 1},
    --   confidence_stats_per_verdict: {confirm: {mean, p25, p50, p75}, ...}
    -- }

    -- B. Forward returns (prices_daily 기반 — past matches의 향후 N개월 수익률)
    forward_returns     JSONB,
    -- {
    --   horizons: [30, 90, 180, 365],
    --   by_verdict: {confirm: {n, mean_pct, p50_pct, hit_2x_rate, hit_5x_rate}, ...},
    --   by_category: {수익성_급전환: {...}, ...},
    --   by_confidence_bucket: {0.7-0.75: {...}, ...}
    -- }

    -- C. Calibration (LLM verdict가 confidence를 예측하는가)
    calibration         JSONB,
    -- {
    --   brier_score: 0.18,
    --   calibration_buckets: [{bin: [0.7, 0.75], n: 5, actual_confirm_rate: 0.4}, ...],
    --   spearman_corr: -0.02  -- confidence vs confirm rate correlation
    -- }

    -- D. Library recall (point-in-time time-travel)
    library_recall      JSONB,
    -- {
    --   lookback_days: [90, 180, 365],
    --   by_lookback: [
    --     {days: 90, n_tested: 49, n_flagged: 30, recall: 0.61, mean_confidence: 0.78},
    --     ...
    --   ],
    --   per_stock: [{ticker, rise_start_date, flagged_at_lookback: [false, true, true]}, ...]
    -- }

    -- E. Top-line KPI (대시보드 카드용)
    summary             JSONB,
    -- {
    --   overall_health: "yellow",
    --   issues: ["수익성_급전환 카테고리 confirm率 0%", "Confidence calibration broken"],
    --   key_metrics: {recall_90d: 0.61, precision_confirm: 0.75, ...}
    -- }

    notes               TEXT
);

CREATE INDEX IF NOT EXISTS idx_hundredx_eval_runs_at
    ON hundredx_evaluation_runs (run_at DESC);

CREATE INDEX IF NOT EXISTS idx_hundredx_eval_runs_kind
    ON hundredx_evaluation_runs (run_kind, run_at DESC);

COMMENT ON TABLE hundredx_evaluation_runs IS
    '평가 인프라: scanner/matching 파이프라인의 정확도/캘리브레이션/recall을 측정해 시계열로 저장. '
    '한 row = 한 번의 evaluation 실행. scanner 룰 변경 전후 효과 측정에 사용.';
