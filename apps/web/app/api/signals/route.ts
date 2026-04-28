export const runtime = 'edge'

import { createServerClient } from '@/lib/supabase'

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url)
  const goldenOnly = searchParams.get('golden') === 'true'
  const days = Number(searchParams.get('days') ?? 7)
  const limit = Math.min(Number(searchParams.get('limit') ?? 20), 100)

  const supabase = createServerClient()
  const since = new Date(Date.now() - days * 86400_000).toISOString()

  let query = supabase
    .from('trigger_events')
    .select('*')
    .gte('detected_at', since)
    .order('detected_at', { ascending: false })
    .limit(limit)

  if (goldenOnly) query = query.eq('golden', true)

  const { data, error } = await query
  if (error) return Response.json({ error: error.message }, { status: 500 })

  const tickers = [...new Set((data ?? []).map(r => r.ticker))]

  const [stocksRes, scoresRes] = await Promise.all([
    tickers.length > 0
      ? supabase.from('stocks').select('ticker, name_kr, name_en, market').in('ticker', tickers)
      : Promise.resolve({ data: [] }),
    tickers.length > 0
      ? supabase
          .from('screen_scores')
          .select('ticker, score_10x, passed, growth, momentum, quality, sponsorship, scores_by_filter')
          .in('ticker', tickers)
          .gte('run_date', new Date(Date.now() - 7 * 86400_000).toISOString().slice(0, 10))
          .order('run_date', { ascending: false })
      : Promise.resolve({ data: [] }),
  ])

  const stockMap = Object.fromEntries(((stocksRes.data as { ticker: string }[] | null) ?? []).map((s: { ticker: string }) => [s.ticker, s]))

  // Take only the most recent score per ticker
  const seenScoreTickers = new Set<string>()
  const scoreMap: Record<string, { score_10x: number | null; passed: boolean; growth: number; momentum: number; quality: number; sponsorship: number; scores_by_filter: Record<string, number> | null }> = {}
  for (const row of (scoresRes.data ?? []) as { ticker: string; score_10x: number | null; passed: boolean; growth: number; momentum: number; quality: number; sponsorship: number; scores_by_filter: Record<string, number> | null }[]) {
    if (!seenScoreTickers.has(row.ticker)) {
      seenScoreTickers.add(row.ticker)
      scoreMap[row.ticker] = row
    }
  }

  const merged = (data ?? []).map(r => ({
    ...r,
    stocks: stockMap[r.ticker] ?? null,
    score: scoreMap[r.ticker] ?? null,
  }))
  return Response.json(merged)
}
