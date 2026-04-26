export const runtime = 'edge'

import { createServerClient } from '@/lib/supabase'
import type { WatchlistStatus } from '@stock/shared'

export async function GET(req: Request) {
  const url = new URL(req.url)
  const status = (url.searchParams.get('status') ?? 'green') as WatchlistStatus

  const supabase = createServerClient()
  const [wlRes, stocksRes] = await Promise.all([
    supabase.from('watchlist').select('*').eq('status', status).order('added_at', { ascending: false }),
    supabase.from('screen_scores')
      .select('ticker, score_10x, percentile')
      .order('run_date', { ascending: false })
      .limit(2000),
  ])

  if (wlRes.error) return Response.json({ error: wlRes.error.message }, { status: 500 })

  const wl = wlRes.data ?? []
  const tickers = [...new Set(wl.map(r => r.ticker))]
  const { data: nameData } = tickers.length > 0
    ? await supabase.from('stocks').select('ticker, name_kr, name_en').in('ticker', tickers)
    : { data: [] }
  const nameMap = Object.fromEntries((nameData ?? []).map(s => [s.ticker, { name_kr: s.name_kr, name_en: s.name_en }]))

  const scoreMap: Record<string, { score_10x: number; percentile: number }> = {}
  for (const s of (stocksRes.data ?? [])) {
    if (!scoreMap[s.ticker]) scoreMap[s.ticker] = { score_10x: s.score_10x, percentile: s.percentile }
  }

  const merged = wl.map(item => ({
    ...item,
    name_kr: nameMap[item.ticker]?.name_kr ?? null,
    name_en: nameMap[item.ticker]?.name_en ?? null,
    score_10x: scoreMap[item.ticker]?.score_10x ?? null,
    percentile: scoreMap[item.ticker]?.percentile ?? null,
  }))
  return Response.json(merged)
}

export async function POST(req: Request) {
  const body = await req.json() as {
    ticker: string
    status?: string
    notes?: string
    target_price?: number
    stop_loss?: number
    position_size_plan?: string
  }

  const supabase = createServerClient()
  const { data, error } = await supabase
    .from('watchlist')
    .insert({
      ticker: body.ticker,
      status: (body.status ?? 'candidate') as WatchlistStatus,
      notes: body.notes ?? null,
      target_price: body.target_price ?? null,
      stop_loss: body.stop_loss ?? null,
      position_size_plan: body.position_size_plan ?? null,
    })
    .select()
    .single()

  if (error) return Response.json({ error: error.message }, { status: 500 })
  return Response.json(data, { status: 201 })
}
