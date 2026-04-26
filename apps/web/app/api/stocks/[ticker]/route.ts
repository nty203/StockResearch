export const runtime = 'edge'

import { createServerClient } from '@/lib/supabase'

function pctChange(newVal: number | null, oldVal: number | null): number | null {
  if (oldVal == null || oldVal === 0 || newVal == null) return null
  return ((newVal - oldVal) / Math.abs(oldVal)) * 100
}

export async function GET(_req: Request, { params }: { params: Promise<{ ticker: string }> }) {
  const { ticker } = await params
  const supabase = createServerClient()

  const cutoff = new Date(Date.now() - 300 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10)

  const [stockRes, scoreRes, agentRes, eventsRes, finsRes, pricesRes] = await Promise.all([
    supabase.from('stocks').select('*').eq('ticker', ticker).maybeSingle(),
    supabase.from('screen_scores').select('*').eq('ticker', ticker).order('run_date', { ascending: false }).limit(1).maybeSingle(),
    supabase.from('agent_scores').select('*').eq('ticker', ticker).order('created_at', { ascending: false }).limit(5),
    supabase.from('trigger_events').select('*').eq('ticker', ticker).order('detected_at', { ascending: false }).limit(20),
    supabase.from('financials_q').select('fq,revenue,op_income,op_margin,roe,roic,fcf,debt_ratio').eq('ticker', ticker).order('fq', { ascending: false }).limit(8),
    supabase.from('prices_daily').select('date,close,volume').eq('ticker', ticker).gte('date', cutoff).order('date', { ascending: false }).limit(252),
  ])

  if (stockRes.error) return Response.json({ error: stockRes.error.message }, { status: 500 })

  // Compute derived financial metrics
  const fins = finsRes.data ?? []
  const sum = (rows: typeof fins, key: keyof typeof fins[0]) =>
    rows.reduce((acc, r) => acc + ((r[key] as number | null) ?? 0), 0) || null

  const ttm = fins.slice(0, 4)
  const prev = fins.slice(4, 8)
  const revenue_ttm = ttm.length > 0 ? sum(ttm, 'revenue') : null
  const revenue_prev = prev.length > 0 ? sum(prev, 'revenue') : null
  const latest = fins[0] ?? null
  const latestPrev = fins[1] ?? null

  const financials = {
    quarters: fins,
    revenue_ttm,
    revenue_prev,
    rev_growth_pct: pctChange(revenue_ttm, revenue_prev),
    op_margin: latest?.op_margin ?? null,
    op_margin_prev: latestPrev?.op_margin ?? null,
    roic: latest?.roic ?? null,
    fcf: latest?.fcf ?? null,
    debt_ratio: latest?.debt_ratio ?? null,
    roe: latest?.roe ?? null,
  }

  // Compute price context
  const prices = pricesRes.data ?? []
  const current = prices[0]?.close ?? null
  const high_52w = prices.length > 0 ? Math.max(...prices.map(p => p.close)) : null
  const pct_from_high = current != null && high_52w != null && high_52w > 0
    ? ((high_52w - current) / high_52w) * 100
    : null
  const recent20 = prices.slice(0, 20)
  const avg_vol = recent20.length > 0 ? recent20.reduce((a, p) => a + (p.volume ?? 0), 0) / recent20.length : null
  const avg_price = recent20.length > 0 ? recent20.reduce((a, p) => a + p.close, 0) / recent20.length : null
  const avg_daily_value = avg_vol != null && avg_price != null && avg_vol > 0 ? avg_vol * avg_price : null

  const priceContext = { current, high_52w, pct_from_high, avg_daily_value }

  return Response.json({
    stock: stockRes.data,
    score: scoreRes.data ?? null,
    agentScores: agentRes.data ?? [],
    events: eventsRes.data ?? [],
    financials,
    priceContext,
  })
}
