-- Phase 0: Survivorship-free 학습 데이터
CREATE TABLE IF NOT EXISTS pptr_training_samples (
    id              BIGSERIAL PRIMARY KEY,
    ticker          TEXT NOT NULL,
    snapshot_date   DATE NOT NULL,
    market          TEXT NOT NULL,
    category        TEXT NOT NULL DEFAULT '미분류',
    -- Labels
    label_10x_24m   SMALLINT NOT NULL DEFAULT 0,  -- 24개월 내 10x 달성
    label_5x_24m    SMALLINT NOT NULL DEFAULT 0,  -- 24개월 내 5x 달성
    label_2x_12m    SMALLINT NOT NULL DEFAULT 0,  -- 12개월 내 2x 달성
    -- Context
    peak_multiplier NUMERIC(10,3),
    trough_date     DATE,
    peak_date       DATE,
    is_delisted     BOOLEAN DEFAULT FALSE,
    notes           TEXT DEFAULT '',
    -- Walk-forward split (computed column for easy filtering)
    split           TEXT GENERATED ALWAYS AS (
        CASE
            WHEN snapshot_date < '2019-01-01' THEN 'train'
            WHEN snapshot_date < '2019-07-01' THEN 'embargo_1'
            WHEN snapshot_date < '2023-01-01' THEN 'val'
            WHEN snapshot_date < '2023-07-01' THEN 'embargo_2'
            ELSE 'test'
        END
    ) STORED,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (ticker, snapshot_date)
);

CREATE INDEX IF NOT EXISTS idx_training_samples_split ON pptr_training_samples (split);
CREATE INDEX IF NOT EXISTS idx_training_samples_category ON pptr_training_samples (category);
CREATE INDEX IF NOT EXISTS idx_training_samples_label ON pptr_training_samples (label_10x_24m);

-- Phase 1: LightGBM 모델 버전 관리
CREATE TABLE IF NOT EXISTS pptr_model_versions (
    id              BIGSERIAL PRIMARY KEY,
    version_tag     TEXT NOT NULL UNIQUE,  -- e.g. "lgbm_20260524_1430"
    model_path      TEXT,
    n_train         INT,
    n_val           INT,
    brier_val       NUMERIC(8,4),
    auc_val         NUMERIC(8,4),
    best_iteration  INT,
    feature_importances  JSONB DEFAULT '{}',
    trained_at      TIMESTAMPTZ,
    is_production   BOOLEAN DEFAULT FALSE,  -- 현재 프로덕션 배포 버전
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 프로덕션 버전은 1개만 (trigger로 보장)
CREATE OR REPLACE FUNCTION set_single_production_model()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.is_production = TRUE THEN
        UPDATE pptr_model_versions SET is_production = FALSE
        WHERE id != NEW.id AND is_production = TRUE;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_single_production ON pptr_model_versions;
CREATE TRIGGER trg_single_production
    AFTER INSERT OR UPDATE ON pptr_model_versions
    FOR EACH ROW EXECUTE FUNCTION set_single_production_model();

-- Phase 3: 백테스트 결과 이력
CREATE TABLE IF NOT EXISTS backtest_runs (
    id                  BIGSERIAL PRIMARY KEY,
    run_at              TIMESTAMPTZ DEFAULT NOW(),
    start_date          DATE NOT NULL,
    end_date            DATE NOT NULL,
    n_days              INT,
    initial_cash        BIGINT DEFAULT 100000000,
    -- Core metrics
    total_return        NUMERIC(10,4),
    annualized_return   NUMERIC(10,4),
    sharpe_ratio        NUMERIC(8,3),
    sortino_ratio       NUMERIC(8,3),
    max_drawdown        NUMERIC(8,4),
    calmar_ratio        NUMERIC(8,3),
    win_rate            NUMERIC(8,4),
    avg_r_multiple      NUMERIC(8,3),
    ann_volatility      NUMERIC(8,4),
    -- Calibration
    brier_score         NUMERIC(8,4),
    -- Governance gates
    deflated_sharpe     NUMERIC(8,4),
    pbo                 NUMERIC(8,4),
    passed_governance   BOOLEAN DEFAULT FALSE,
    -- Trade stats
    n_trades            INT,
    n_signals_received  INT,
    n_signals_rejected  INT,
    rejection_reasons   JSONB DEFAULT '{}',
    -- Config
    config              JSONB DEFAULT '{}',
    model_version_id    BIGINT REFERENCES pptr_model_versions(id),
    notes               TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_backtest_runs_dates ON backtest_runs (start_date, end_date);
CREATE INDEX IF NOT EXISTS idx_backtest_runs_governance ON backtest_runs (passed_governance);

-- Phase 5: Paper trading 신호 (수동 체결 대기)
CREATE TABLE IF NOT EXISTS paper_trade_signals (
    id              BIGSERIAL PRIMARY KEY,
    signal_date     DATE NOT NULL,
    signal_type     TEXT NOT NULL,   -- BUY_SIGNAL | EXIT_SIGNAL | WATCH
    ticker          TEXT NOT NULL,
    category        TEXT,
    confidence      NUMERIC(6,3),
    suggested_size_pct  NUMERIC(6,4),
    reason          TEXT,
    details         JSONB DEFAULT '{}',
    status          TEXT DEFAULT 'pending',  -- pending | filled | cancelled
    filled_price    NUMERIC(12,2),
    filled_at       TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_paper_signals_date ON paper_trade_signals (signal_date);
CREATE INDEX IF NOT EXISTS idx_paper_signals_status ON paper_trade_signals (status);

-- Paper trading 실제 포지션
CREATE TABLE IF NOT EXISTS paper_trades (
    id              BIGSERIAL PRIMARY KEY,
    ticker          TEXT NOT NULL,
    category        TEXT,
    entry_date      DATE,
    entry_price     NUMERIC(12,2),
    shares          NUMERIC(12,4),
    position_value  NUMERIC(15,2),
    status          TEXT DEFAULT 'open',    -- open | closed
    exit_date       DATE,
    exit_price      NUMERIC(12,2),
    exit_reason     TEXT,
    -- Tracking
    last_price      NUMERIC(12,2),
    max_close_since_entry NUMERIC(12,2),
    current_confidence NUMERIC(6,3),
    unrealized_pnl  NUMERIC(15,2),
    realized_pnl    NUMERIC(15,2),
    signal_id       BIGINT REFERENCES paper_trade_signals(id),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_paper_trades_status ON paper_trades (status);
CREATE INDEX IF NOT EXISTS idx_paper_trades_ticker ON paper_trades (ticker);

-- Phase 3: 포트폴리오 일별 스냅샷 (백테스트 + paper trading 공용)
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id              BIGSERIAL PRIMARY KEY,
    snapshot_date   DATE NOT NULL,
    run_type        TEXT NOT NULL,    -- 'backtest' | 'paper'
    run_id          BIGINT,           -- backtest_runs.id 또는 NULL
    total_value     BIGINT,
    cash            BIGINT,
    equity_value    BIGINT,
    n_positions     INT,
    daily_return    NUMERIC(10,6),
    cumulative_return NUMERIC(10,6),
    max_drawdown    NUMERIC(10,6),
    positions       JSONB DEFAULT '[]',
    category_weights JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_date ON portfolio_snapshots (snapshot_date, run_type);

-- 코멘트
COMMENT ON TABLE pptr_training_samples IS 'Survivorship-free 학습 데이터 (상장폐지 포함)';
COMMENT ON TABLE pptr_model_versions IS 'LightGBM 모델 버전 관리 (is_production=TRUE가 현재 배포)';
COMMENT ON TABLE backtest_runs IS '백테스트 결과 이력 (passed_governance=TRUE여야 real money 투입)';
COMMENT ON TABLE paper_trade_signals IS 'Paper trading 매수/매도 신호 (수동 체결 대기)';
COMMENT ON TABLE paper_trades IS 'Paper trading 실제 포지션 관리';
COMMENT ON TABLE portfolio_snapshots IS '백테스트/paper trading 일별 포트폴리오 스냅샷';
