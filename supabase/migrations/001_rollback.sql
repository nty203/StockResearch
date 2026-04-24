-- Rollback 001_init.sql
-- Run: psql $DATABASE_URL -f supabase/migrations/001_rollback.sql

SELECT cron.unschedule('queue-timeout-reset');

DROP TABLE IF EXISTS failure_cases      CASCADE;
DROP TABLE IF EXISTS settings           CASCADE;
DROP TABLE IF EXISTS pipeline_runs      CASCADE;
DROP TABLE IF EXISTS analysis_queue     CASCADE;
DROP TABLE IF EXISTS watchlist          CASCADE;
DROP TABLE IF EXISTS trigger_events     CASCADE;
DROP TABLE IF EXISTS agent_scores       CASCADE;
DROP TABLE IF EXISTS screen_scores      CASCADE;
DROP TABLE IF EXISTS news               CASCADE;
DROP TABLE IF EXISTS filings            CASCADE;
DROP TABLE IF EXISTS financials_q       CASCADE;
DROP TABLE IF EXISTS prices_daily       CASCADE;
DROP TABLE IF EXISTS stocks             CASCADE;
