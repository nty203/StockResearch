export const runtime = 'edge'

import { createServerClient } from '@/lib/supabase'

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url)
  const limit = Math.min(Number(searchParams.get('limit') ?? 30), 100)

  const supabase = createServerClient()

  // Get the latest available run_date (may lag today if workflow ran yesterday)
  const { data: latest } = await supabase
    .from('screen_scores')
    .select('run_date')
    .order('run_date', { ascending: false })
    .limit(1)
    .single()

  const runDate = latest?.run_date ?? new Date().toISOString().slice(0, 10)

  const [scoresRes, namesRes] = await Promise.all([
    supabase
      .from('screen_scores')
      .select('ticker, score_10x, growth, momentum, quality, sponsorship, value, safety, size, market_gate, passed, run_date')
      .eq('run_date', runDate)
      .order('score_10x', { ascending: false })
      .limit(limit),
    supabase
      .from('stocks')
      .select('ticker, name_kr, name_en'),
  ])

  if (scoresRes.error) return Response.json({ error: scoresRes.error.message }, { status: 500 })

  const tickers = (scoresRes.data ?? []).map(r => r.ticker)

  // Fetch latest rise_category per ticker from trigger_events
  const categoryMap: Record<string, string | null> = {}
  if (tickers.length > 0) {
    const { data: evData } = await supabase
      .from('trigger_events')
      .select('ticker, rise_category, detected_at')
      .in('ticker', tickers)
      .not('rise_category', 'is', null)
      .order('detected_at', { ascending: false })
      .limit(tickers.length * 5)

    // Keep only the most recent per ticker
    for (const ev of (evData ?? [])) {
      if (!(ev.ticker in categoryMap)) {
        categoryMap[ev.ticker] = ev.rise_category
      }
    }
  }

  const nameMap = Object.fromEntries((namesRes.data ?? []).map(s => [s.ticker, { name_kr: s.name_kr, name_en: s.name_en }]))
  const data = (scoresRes.data ?? []).map(row => ({
    ...row,
    name_kr: nameMap[row.ticker]?.name_kr ?? null,
    name_en: nameMap[row.ticker]?.name_en ?? null,
    rise_category: categoryMap[row.ticker] ?? null,
  }))

  return Response.json(data)
}
