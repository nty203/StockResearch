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
      .select('ticker, name_kr'),
  ])

  if (scoresRes.error) return Response.json({ error: scoresRes.error.message }, { status: 500 })

  const nameMap = Object.fromEntries((namesRes.data ?? []).map(s => [s.ticker, s.name_kr]))
  const data = (scoresRes.data ?? []).map(row => ({ ...row, name_kr: nameMap[row.ticker] ?? null }))

  return Response.json(data)
}
