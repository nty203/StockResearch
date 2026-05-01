-- ============================================================
-- Drop legacy tables (no longer used after 100x-only refocus)
-- PR1 merged 2026-04-30; apply after 7+ days stable ops
--
-- BEFORE RUNNING: confirm zero active references via
--   SELECT table_name, pg_total_relation_size(table_name::regclass) AS bytes
--   FROM information_schema.tables
--   WHERE table_name IN ('screen_scores','agent_scores','analysis_queue',
--                         'watchlist','backtest_runs','backtest_results','trigger_events')
--     AND table_schema = 'public';
-- ============================================================

DROP TABLE IF EXISTS trigger_events      CASCADE;
DROP TABLE IF EXISTS screen_scores       CASCADE;
DROP TABLE IF EXISTS agent_scores        CASCADE;
DROP TABLE IF EXISTS analysis_queue      CASCADE;
DROP TABLE IF EXISTS watchlist           CASCADE;
DROP TABLE IF EXISTS backtest_runs       CASCADE;
DROP TABLE IF EXISTS backtest_results    CASCADE;
