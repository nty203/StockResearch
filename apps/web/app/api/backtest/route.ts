export const runtime = 'edge'

import { createServerClient } from '@/lib/supabase'

export async function GET() {
  const supabase = createServerClient()

  // Fetch last 5 runs with their results
  const { data: runs, error: runsError } = await supabase
    .from('backtest_runs')
    .select('id, run_date, dart_used, triggered_by, created_at')
    .order('created_at', { ascending: false })
    .limit(5)

  if (runsError) return Response.json({ error: runsError.message }, { status: 500 })

  if (!runs || runs.length === 0) {
    return Response.json({ runs: [], results: [] })
  }

  const latestRunId = runs[0].id

  const { data: results, error: resultsError } = await supabase
    .from('backtest_results')
    .select('*')
    .eq('run_id', latestRunId)
    .order('is_target', { ascending: false })

  if (resultsError) return Response.json({ error: resultsError.message }, { status: 500 })

  return Response.json({ runs, results: results ?? [] })
}

export async function POST() {
  const GITHUB_PAT  = process.env.GITHUB_PAT
  const GITHUB_REPO = process.env.GITHUB_REPO
  if (!GITHUB_PAT || !GITHUB_REPO) {
    return Response.json({ error: 'GitHub credentials not configured' }, { status: 500 })
  }

  const res = await fetch(
    `https://api.github.com/repos/${GITHUB_REPO}/actions/workflows/validate-backtest.yml/dispatches`,
    {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${GITHUB_PAT}`,
        Accept: 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ ref: 'main' }),
    },
  )

  if (!res.ok) {
    const text = await res.text()
    return Response.json({ error: text }, { status: res.status })
  }
  return Response.json({ ok: true })
}
