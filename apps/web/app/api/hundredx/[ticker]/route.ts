export const runtime = 'edge'

import { createServerClient } from '@/lib/supabase'

export async function GET(_req: Request, { params }: { params: Promise<{ ticker: string }> }) {
  const { ticker } = await params
  const supabase = createServerClient()

  const [matchesRes, stockRes, libRes] = await Promise.all([
    supabase
      .from('hundredx_category_matches')
      .select('*')
      .eq('ticker', ticker)
      .order('confidence', { ascending: false }),
    supabase
      .from('stocks')
      .select('ticker, name_kr, name_en, market, sector_tag')
      .eq('ticker', ticker)
      .single(),
    supabase
      .from('hundredx_library_stocks')
      .select('*'),
  ])

  if (matchesRes.error) return Response.json({ error: matchesRes.error.message }, { status: 500 })

  type Match = {
    ticker: string
    category: string
    confidence: number
    evidence: Array<{ source_type: string; source_id: string; text_excerpt: string; date: string | null; amount: number | null }> | null
    first_detected_at: string | null
    detected_at: string
    exited_at: string | null
    analog_ticker: string | null
    analog_date: string | null
    analog_multiplier: number | null
    price_baseline_date: string | null
    price_baseline_close: number | null
    price_latest_date: string | null
    price_latest_close: number | null
    price_peak_date: string | null
    price_peak_close: number | null
    price_current_multiplier: number | null
    price_change_pct: number | null
    price_peak_multiplier: number | null
    price_peak_change_pct: number | null
    price_performance_updated_at: string | null
  }
  type LibStock = { ticker: string; category: string; pre_rise_signals: Record<string, unknown> | null; rise_start_date: string | null; peak_multiplier: number | null; notes: string | null }

  const matches = (matchesRes.data ?? []) as Match[]
  const lib = ((libRes.data ?? []) as LibStock[])
  const libByTicker: Record<string, LibStock> = Object.fromEntries(lib.map(l => [l.ticker, l]))

  const enriched = matches.map(m => ({
    category: m.category,
    confidence: m.confidence,
    evidence: m.evidence ?? [],
    first_detected_at: m.first_detected_at,
    detected_at: m.detected_at,
    exited_at: m.exited_at,
    analog: m.analog_ticker ? {
      ticker: m.analog_ticker,
      date: m.analog_date,
      multiplier: m.analog_multiplier,
      notes: libByTicker[m.analog_ticker]?.notes ?? null,
    } : null,
    price_performance: m.price_current_multiplier != null || m.price_change_pct != null ? {
      baseline_date: m.price_baseline_date,
      baseline_close: m.price_baseline_close,
      latest_date: m.price_latest_date,
      latest_close: m.price_latest_close,
      peak_date: m.price_peak_date,
      peak_close: m.price_peak_close,
      current_multiplier: m.price_current_multiplier,
      change_pct: m.price_change_pct,
      peak_multiplier: m.price_peak_multiplier,
      peak_change_pct: m.price_peak_change_pct,
      updated_at: m.price_performance_updated_at,
    } : null,
  }))

  return Response.json({
    ticker,
    stock: stockRes.data ?? null,
    matches: enriched,
  })
}
