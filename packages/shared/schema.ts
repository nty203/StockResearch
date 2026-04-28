// Auto-generated types matching supabase/migrations/001_init.sql
// Regenerate with: npx supabase gen types typescript --local > packages/shared/schema.ts

export type Market = 'KOSPI' | 'KOSDAQ' | 'NYSE' | 'NASDAQ'
export type QueueStatus = 'PENDING' | 'CLAIMED' | 'COMPLETED' | 'FAILED' | 'INVALID'
export type WatchlistStatus = 'candidate' | 'yellow' | 'green'
export type PipelineStage = 'universe' | 'prices' | 'financials' | 'filings' | 'news' | 'scores' | 'queue' | 'notify' | 'queue_reset' | 'hundredx'

export type Stock = {
  id: string
  ticker: string
  market: Market
  name_kr: string | null
  name_en: string | null
  sector_wics: string | null
  industry: string | null
  sector_tag: string | null   // 방산/전력기기/바이오/로봇/원전 등
  is_active: boolean
  created_at: string
}

export type PriceDaily = {
  ticker: string
  date: string
  open: number | null
  high: number | null
  low: number | null
  close: number
  volume: number | null
  adj_close: number | null
}

export type FinancialQ = {
  id: string
  ticker: string
  fq: string            // format: 'YYYYQ[1-4]', e.g. '2023Q1'
  revenue: number | null
  op_income: number | null
  net_income: number | null
  op_margin: number | null
  roe: number | null
  roic: number | null
  fcf: number | null
  debt_ratio: number | null
  interest_coverage: number | null
  order_backlog: number | null      // 수주잔고 (원)
  order_backlog_prev: number | null // 전기 수주잔고 (YoY 성장률용)
  created_at: string
}

export type Filing = {
  id: string
  ticker: string
  source: 'DART' | 'SEC'
  filing_type: string
  filed_at: string
  url: string
  headline: string
  raw_text: string | null
  keywords: string[]
  parsed_amount: number | null
  parsed_customer: string | null
  created_at: string
}

export type News = {
  id: string
  ticker: string
  source: string
  published_at: string
  url: string
  title: string
  summary: string | null
  lang: 'ko' | 'en'
}

export type ScreenScore = {
  ticker: string
  run_date: string
  growth: number
  momentum: number
  quality: number
  sponsorship: number
  value: number
  safety: number
  size: number
  market_gate: number
  score_10x: number
  percentile: number
  passed: boolean
  failed_filters: string[]
  scores_by_filter: Record<string, number> | null
  created_at: string
}

export type AgentScore = {
  id: string
  ticker: string
  run_date: string
  prompt_type: string
  demand_score: number | null
  moat_score: number | null
  trigger_score: number | null
  narrative_md: string | null
  risks_md: string | null
  bull_bear_ratio: number | null
  agent_model: string | null
  created_at: string
}

export type RiseCategory =
  | '수주잔고_선행'
  | '빅테크_파트너'
  | '임상_파이프라인'
  | '플랫폼_독점'
  | '정책_수혜'
  | '수익성_급전환'
  | '공급_병목'

export type TriggerEvent = {
  id: string
  ticker: string
  event_type: string
  detected_at: string
  confidence: number
  source_filing_id: string | null
  matched_keywords: string[]
  summary: string
  golden: boolean
  rise_category: RiseCategory | null
}

export type Watchlist = {
  id: string
  ticker: string
  status: WatchlistStatus
  added_at: string
  notes: string | null
  target_price: number | null
  stop_loss: number | null
  position_size_plan: string | null
}

export type AnalysisQueue = {
  id: string
  ticker: string
  prompt_type: string
  status: QueueStatus
  created_at: string
  claimed_at: string | null
  storage_path_prompt: string | null
  storage_path_result: string | null
  claimed_by: string | null
}

export type PipelineRun = {
  id: string
  stage: PipelineStage
  started_at: string
  ended_at: string | null
  status: 'running' | 'success' | 'error'
  rows_processed: number | null
  error_msg: string | null
  github_run_id: string | null
}

export type Setting = {
  key: string
  value_json: unknown
  updated_at: string
}

export type FailureCase = {
  id: string
  ticker: string
  peak_at: string
  peak_price: number
  trough_at: string
  trough_price: number
  early_signals: string[]
  lesson_md: string | null
}

export type BacktestRun = {
  id: string
  run_date: string
  triggered_by: string | null
  dart_used: boolean
  created_at: string
}

export type BacktestResult = {
  id: string
  run_id: string
  ticker: string
  name: string | null
  market: string | null
  snapshot_date: string
  peak_date: string | null
  actual_x: number | null
  score_10x: number | null
  passed: boolean
  failed_filters: string[] | null
  cats: Record<string, number> | null
  price_at_snapshot: number | null
  rs_score: number | null
  is_target: boolean
  created_at: string
}

export type HundredxLibraryStock = {
  id: string
  ticker: string
  category: RiseCategory
  pre_rise_signals: Record<string, unknown> | null
  earliest_signal_date: string | null
  rise_start_date: string | null
  peak_multiplier: number | null
  notes: string | null
  created_at: string
}

export type HundredxEvidence = {
  source_type: string
  source_id: string
  text_excerpt: string
  date: string | null
  amount: number | null
}

export type HundredxCategoryMatch = {
  id: string
  ticker: string
  category: RiseCategory
  confidence: number
  evidence: HundredxEvidence[]
  first_detected_at: string | null
  detected_at: string
  exited_at: string | null
  alert_sent_at: string | null
  analog_ticker: string | null
  analog_date: string | null
  analog_multiplier: number | null
}

// Supabase Database type for createClient<Database>
export type Database = {
  public: {
    Tables: {
      stocks:           { Row: Stock;          Insert: Omit<Stock, 'id' | 'created_at'>;          Update: Partial<Omit<Stock, 'id'>>;          Relationships: never[] }
      prices_daily:     { Row: PriceDaily;     Insert: PriceDaily;                                Update: Partial<PriceDaily>;                 Relationships: never[] }
      financials_q:     { Row: FinancialQ;     Insert: Omit<FinancialQ, 'id' | 'created_at'>;     Update: Partial<Omit<FinancialQ, 'id'>>;     Relationships: never[] }
      filings:          { Row: Filing;         Insert: Omit<Filing, 'id' | 'created_at'>;          Update: Partial<Omit<Filing, 'id'>>;         Relationships: never[] }
      news:             { Row: News;           Insert: Omit<News, 'id'>;                           Update: Partial<Omit<News, 'id'>>;            Relationships: never[] }
      screen_scores:    { Row: ScreenScore;    Insert: Omit<ScreenScore, 'created_at'>;            Update: Partial<ScreenScore>;                Relationships: never[] }
      agent_scores:     { Row: AgentScore;     Insert: Omit<AgentScore, 'id' | 'created_at'>;      Update: Partial<Omit<AgentScore, 'id'>>;     Relationships: never[] }
      trigger_events:   { Row: TriggerEvent;   Insert: Omit<TriggerEvent, 'id'>;                   Update: Partial<Omit<TriggerEvent, 'id'>>;   Relationships: never[] }
      watchlist:        { Row: Watchlist;      Insert: Omit<Watchlist, 'id' | 'added_at'>;         Update: Partial<Omit<Watchlist, 'id'>>;      Relationships: never[] }
      analysis_queue:   { Row: AnalysisQueue;  Insert: Omit<AnalysisQueue, 'id' | 'created_at'>;  Update: Partial<Omit<AnalysisQueue, 'id'>>;  Relationships: never[] }
      pipeline_runs:    { Row: PipelineRun;    Insert: Omit<PipelineRun, 'id'>;                    Update: Partial<Omit<PipelineRun, 'id'>>;    Relationships: never[] }
      settings:         { Row: Setting;        Insert: Setting;                                    Update: Partial<Setting>;                    Relationships: never[] }
      failure_cases:    { Row: FailureCase;    Insert: Omit<FailureCase, 'id'>;                    Update: Partial<Omit<FailureCase, 'id'>>;    Relationships: never[] }
      backtest_runs:    { Row: BacktestRun;    Insert: Omit<BacktestRun, 'id' | 'created_at'>;     Update: Partial<Omit<BacktestRun, 'id'>>;    Relationships: never[] }
      backtest_results: { Row: BacktestResult; Insert: Omit<BacktestResult, 'id' | 'created_at'>; Update: Partial<Omit<BacktestResult, 'id'>>; Relationships: never[] }
      hundredx_library_stocks:    { Row: HundredxLibraryStock;    Insert: Omit<HundredxLibraryStock, 'id' | 'created_at'>;    Update: Partial<Omit<HundredxLibraryStock, 'id'>>;    Relationships: never[] }
      hundredx_category_matches:  { Row: HundredxCategoryMatch;   Insert: Omit<HundredxCategoryMatch, 'id'>;                  Update: Partial<Omit<HundredxCategoryMatch, 'id'>>;  Relationships: never[] }
    }
    Views: { [_ in never]: never }
    Functions: { [_ in never]: never }
    Enums: { [_ in never]: never }
    CompositeTypes: { [_ in never]: never }
  }
}
