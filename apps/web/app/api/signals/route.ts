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
  const { data: stocksData } = tickers.length > 0
    ? await supabase.from('stocks').select('ticker, name_kr, name_en, market').in('ticker', tickers)
    : { data: [] }
  const stockMap = Object.fromEntries((stocksData ?? []).map(s => [s.ticker, s]))

  const merged = (data ?? []).map(r => ({
    ...r,
    stocks: stockMap[r.ticker] ?? null,
  }))
  return Response.json(merged)
}
