export const runtime = 'edge'

import { createServerClient } from '@/lib/supabase'

interface AgentResult {
  demand_score: number
  moat_score: number
  trigger_score: number
  narrative_md?: string
  risks_md?: string
  bull_bear_ratio?: number
}

export async function POST(req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  const body = await req.json() as AgentResult

  const supabase = createServerClient()

  // Get queue item to know ticker + prompt_type
  const { data: item, error: fetchErr } = await supabase
    .from('analysis_queue')
    .select('ticker, prompt_type')
    .eq('id', id)
    .single()

  if (fetchErr || !item) return Response.json({ error: 'Queue item not found' }, { status: 404 })

  const today = new Date().toISOString().slice(0, 10)

  const { error: scoreErr } = await supabase
    .from('agent_scores')
    .upsert({
      ticker: item.ticker,
      run_date: today,
      prompt_type: item.prompt_type,
      demand_score: body.demand_score,
      moat_score: body.moat_score,
      trigger_score: body.trigger_score,
      narrative_md: body.narrative_md ?? null,
      risks_md: body.risks_md ?? null,
      bull_bear_ratio: body.bull_bear_ratio ?? null,
      agent_model: 'manual',
    }, { onConflict: 'ticker,run_date,prompt_type' })

  if (scoreErr) return Response.json({ error: scoreErr.message }, { status: 500 })

  await supabase
    .from('analysis_queue')
    .update({ status: 'COMPLETED' as const })
    .eq('id', id)

  return Response.json({ ok: true })
}
