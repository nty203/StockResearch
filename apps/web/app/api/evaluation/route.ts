export const runtime = 'edge'

import { createServerClient } from '@/lib/supabase'

type EvaluationRun = {
  id: string
  run_at: string
  run_kind: string
  git_commit: string | null
  params: Record<string, unknown> | null
  n_matches_window: number | null
  n_library_stocks: number | null
  window_days: number | null
  diagnostics: Record<string, unknown> | null
  forward_returns: Record<string, unknown> | null
  calibration: Record<string, unknown> | null
  library_recall: Record<string, unknown> | null
  summary: Record<string, unknown> | null
  notes: string | null
}

export async function GET(request: Request) {
  const url = new URL(request.url)
  const limit = Math.min(parseInt(url.searchParams.get('limit') || '10', 10), 50)
  const kind = url.searchParams.get('kind')
  const id = url.searchParams.get('id')

  const client = createServerClient()
  let query = client
    .from('hundredx_evaluation_runs')
    .select('*')
    .order('run_at', { ascending: false })

  if (id) {
    query = query.eq('id', id).limit(1)
  } else {
    if (kind) query = query.eq('run_kind', kind)
    query = query.limit(limit)
  }

  const { data, error } = await query
  if (error) {
    return new Response(JSON.stringify({ error: error.message }), {
      status: 500,
      headers: { 'content-type': 'application/json' },
    })
  }

  const runs = (data as EvaluationRun[]) || []
  return new Response(
    JSON.stringify({ runs, count: runs.length }),
    { headers: { 'content-type': 'application/json' } },
  )
}
