export const runtime = 'edge'

import { createServerClient } from '@/lib/supabase'

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
}

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url)
  const minConfidence = Math.max(0, Math.min(1, Number(searchParams.get('min_confidence') ?? 0.5)))

  const supabase = createServerClient()

  // Active matches only (exited_at IS NULL), above confidence threshold
  const { data: matches, error } = await supabase
    .from('hundredx_category_matches')
    .select('*')
    .is('exited_at', null)
    .gte('confidence', minConfidence)
    .order('confidence', { ascending: false })

  if (error) return Response.json({ error: error.message }, { status: 500 })

  const rows = (matches ?? []) as Match[]
  const tickers = [...new Set(rows.map(r => r.ticker))]

  // Join: stock metadata + active golden_signal cross-link
  const sevenDaysAgo = new Date(Date.now() - 7 * 86400_000).toISOString()
  const [stocksRes, goldenRes] = await Promise.all([
    tickers.length > 0
      ? supabase.from('stocks').select('ticker, name_kr, name_en, market, sector_tag').in('ticker', tickers)
      : Promise.resolve({ data: [] }),
    tickers.length > 0
      ? supabase
          .from('trigger_events')
          .select('ticker, golden, detected_at')
          .in('ticker', tickers)
          .eq('golden', true)
          .gte('detected_at', sevenDaysAgo)
      : Promise.resolve({ data: [] }),
  ])

  type Stock = { ticker: string; name_kr: string | null; name_en: string | null; market: string | null; sector_tag: string | null }
  const stockMap: Record<string, Stock> = Object.fromEntries(((stocksRes.data as Stock[] | null) ?? []).map(s => [s.ticker, s]))
  const goldenSet = new Set(((goldenRes.data as { ticker: string }[] | null) ?? []).map(r => r.ticker))

  // Group by ticker, compute conviction = (len/7)*50 + avg_conf*50
  const byTicker: Record<string, Match[]> = {}
  for (const m of rows) {
    if (!byTicker[m.ticker]) byTicker[m.ticker] = []
    byTicker[m.ticker].push(m)
  }

  const result = Object.entries(byTicker).map(([ticker, cats]) => {
    const breadth = (cats.length / 7) * 50
    const avgConf = cats.reduce((s, c) => s + c.confidence, 0) / cats.length
    const conviction = breadth + avgConf * 50

    // First-signal date = oldest first_detected_at across categories
    const firstSignal = cats
      .map(c => c.first_detected_at)
      .filter((d): d is string => !!d)
      .sort()[0] ?? null

    return {
      ticker,
      stock: stockMap[ticker] ?? null,
      conviction: Math.round(conviction * 10) / 10,
      first_signal_at: firstSignal,
      golden_active: goldenSet.has(ticker),
      categories: cats.map(c => ({
        category: c.category,
        confidence: c.confidence,
        evidence: c.evidence ?? [],
        first_detected_at: c.first_detected_at,
        detected_at: c.detected_at,
        analog: c.analog_ticker ? {
          ticker: c.analog_ticker,
          date: c.analog_date,
          multiplier: c.analog_multiplier,
        } : null,
      })).sort((a, b) => b.confidence - a.confidence),
    }
  })

  result.sort((a, b) => b.conviction - a.conviction)

  return Response.json({ results: result, count: result.length })
}
