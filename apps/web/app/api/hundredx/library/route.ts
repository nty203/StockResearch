export const runtime = 'edge'

import { createServerClient } from '@/lib/supabase'

type LibRow = {
  id: string
  ticker: string
  category: string
  pre_rise_signals: Record<string, unknown> | null
  earliest_signal_date: string | null
  rise_start_date: string | null
  peak_multiplier: number | null
  latest_multiplier: number | null
  price_at_rise_start: number | null
  latest_updated_at: string | null
  notes: string | null
  pptr_analysis: Record<string, unknown> | null
}

export async function GET() {
  const supabase = createServerClient()

  const { data: libRows, error } = await supabase
    .from('hundredx_library_stocks')
    .select('*')
    .order('peak_multiplier', { ascending: false, nullsFirst: false })

  if (error) return Response.json({ error: error.message }, { status: 500 })

  const rows = (libRows ?? []) as unknown as LibRow[]
  const tickers = [...new Set(rows.map(r => r.ticker))]

  const namesRes = tickers.length > 0
    ? await supabase.from('stocks').select('ticker, name_kr, name_en, market').in('ticker', tickers)
    : { data: [] as { ticker: string; name_kr: string | null; name_en: string | null; market: string | null }[] }

  type StockMeta = { ticker: string; name_kr: string | null; name_en: string | null; market: string | null }
  const stockMap: Record<string, StockMeta> = Object.fromEntries(((namesRes.data as StockMeta[] | null) ?? []).map(s => [s.ticker, s]))

  // Group by ticker; collapse multi-category rows into one stock entry with categories[]
  const byTicker: Record<string, {
    ticker: string
    name: string | null
    market: string | null
    peak_multiplier: number | null
    latest_multiplier: number | null
    earliest_signal_date: string | null
    rise_start_date: string | null
    price_at_rise_start: number | null
    latest_updated_at: string | null
    categories: Array<{
      category: string
      pre_rise_signals: Record<string, unknown> | null
      notes: string | null
      pptr_analysis: Record<string, unknown> | null
    }>
  }> = {}

  for (const r of rows) {
    if (!byTicker[r.ticker]) {
      const meta = stockMap[r.ticker]
      byTicker[r.ticker] = {
        ticker: r.ticker,
        name: meta?.name_kr ?? meta?.name_en ?? null,
        market: meta?.market ?? null,
        peak_multiplier: r.peak_multiplier,
        latest_multiplier: r.latest_multiplier,
        earliest_signal_date: r.earliest_signal_date,
        rise_start_date: r.rise_start_date,
        price_at_rise_start: r.price_at_rise_start,
        latest_updated_at: r.latest_updated_at,
        categories: [],
      }
    }
    byTicker[r.ticker].categories.push({
      category: r.category,
      pre_rise_signals: r.pre_rise_signals,
      notes: r.notes,
      pptr_analysis: r.pptr_analysis,
    })
  }

  const result = Object.values(byTicker).sort(
    (a, b) => (b.peak_multiplier ?? 0) - (a.peak_multiplier ?? 0)
  )

  return Response.json({ stocks: result, count: result.length })
}
