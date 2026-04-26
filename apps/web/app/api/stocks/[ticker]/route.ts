export const runtime = 'edge'

import { createServerClient } from '@/lib/supabase'

export async function GET(_req: Request, { params }: { params: Promise<{ ticker: string }> }) {
  const { ticker } = await params
  const supabase = createServerClient()

  const [stockRes, scoreRes, agentRes, eventsRes] = await Promise.all([
    supabase.from('stocks').select('*').eq('ticker', ticker).maybeSingle(),
    supabase.from('screen_scores').select('*').eq('ticker', ticker).order('run_date', { ascending: false }).limit(1).maybeSingle(),
    supabase.from('agent_scores').select('*').eq('ticker', ticker).order('created_at', { ascending: false }).limit(5),
    supabase.from('trigger_events').select('*').eq('ticker', ticker).order('detected_at', { ascending: false }).limit(20),
  ])

  if (stockRes.error) return Response.json({ error: stockRes.error.message }, { status: 500 })

  return Response.json({
    stock: stockRes.data,
    score: scoreRes.data ?? null,
    agentScores: agentRes.data ?? [],
    events: eventsRes.data ?? [],
  })
}
