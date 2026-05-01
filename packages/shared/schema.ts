// Auto-generated types matching supabase/migrations/001_init.sql
// Regenerate with: npx supabase gen types typescript --local > packages/shared/schema.ts

export type Market = 'KOSPI' | 'KOSDAQ' | 'NYSE' | 'NASDAQ'
export type PipelineStage = 'universe' | 'prices' | 'financials' | 'filings' | 'news' | 'hundredx'

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

export type RiseCategory =
  | '수주잔고_선행'
  | '빅테크_파트너'
  | '임상_파이프라인'
  | '플랫폼_독점'
  | '정책_수혜'
  | '수익성_급전환'
  | '공급_병목'

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

export type HundredxLibraryStock = {
  id: string
  ticker: string
  category: RiseCategory
  pre_rise_signals: Record<string, unknown> | null
  earliest_signal_date: string | null
  rise_start_date: string | null
  peak_multiplier: number | null
  latest_multiplier: number | null         // 최근 update 시점 가격 기준 배수
  price_at_rise_start: number | null        // rise_start_date 기준가
  latest_updated_at: string | null          // update_library 마지막 실행 시각
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
  fingerprint_score: number | null    // 0-1, similarity to library precedent
  fingerprint_dims: {                  // matched/missing dimensions detail
    matched: string[]
    missing: string[]
    details: Record<string, unknown>
  } | null
  timeline_progress: {                 // trigger sequence timeline match
    library_ticker: string
    library_category: string
    library_peak_multiplier: number | null
    fired_triggers: Array<{
      seq: number
      name: string
      months_from_rise: number
      fired_at_date: string | null
      fired_at_months_ago: number | null
      weight: number
      matched_signals: string[]
    }>
    total_triggers: number
    trajectory_score: number
    current_position_months: number
    next_expected: { seq: number; name: string; months_from_rise: number; expected_in_months: number } | null
  } | null
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
      pipeline_runs:    { Row: PipelineRun;    Insert: Omit<PipelineRun, 'id'>;                    Update: Partial<Omit<PipelineRun, 'id'>>;    Relationships: never[] }
      settings:         { Row: Setting;        Insert: Setting;                                    Update: Partial<Setting>;                    Relationships: never[] }
      hundredx_library_stocks:    { Row: HundredxLibraryStock;    Insert: Omit<HundredxLibraryStock, 'id' | 'created_at'>;    Update: Partial<Omit<HundredxLibraryStock, 'id'>>;    Relationships: never[] }
      hundredx_category_matches:  { Row: HundredxCategoryMatch;   Insert: Omit<HundredxCategoryMatch, 'id'>;                  Update: Partial<Omit<HundredxCategoryMatch, 'id'>>;  Relationships: never[] }
    }
    Views: { [_ in never]: never }
    Functions: { [_ in never]: never }
    Enums: { [_ in never]: never }
    CompositeTypes: { [_ in never]: never }
  }
}
