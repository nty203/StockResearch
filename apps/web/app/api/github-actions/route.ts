export const runtime = 'edge'

// GitHub Actions 워크플로우 실행 상태 조회
// GET /api/github-actions
// Returns: list of workflows with last run status, conclusion, and timestamps

type WorkflowRun = {
  id: number
  status: string
  conclusion: string | null
  created_at: string
  updated_at: string
  html_url: string
  run_number: number
  event: string
}

type WorkflowInfo = {
  id: number
  name: string
  path: string
  state: string
  html_url: string
}

export async function GET() {
  const repo = process.env.GITHUB_REPO ?? ''
  const token = process.env.GITHUB_PAT ?? ''

  if (!repo) {
    return Response.json({ error: 'GITHUB_REPO not configured' }, { status: 500 })
  }

  const headers: Record<string, string> = {
    Accept: 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28',
  }
  if (token) headers['Authorization'] = `Bearer ${token}`

  // 1. 워크플로우 목록 조회
  const wfRes = await fetch(
    `https://api.github.com/repos/${repo}/actions/workflows?per_page=20`,
    { headers }
  )

  if (!wfRes.ok) {
    const text = await wfRes.text()
    return Response.json(
      { error: `GitHub API error: ${wfRes.status} ${text}` },
      { status: wfRes.status }
    )
  }

  const wfData = await wfRes.json() as { workflows: WorkflowInfo[] }
  const workflows = wfData.workflows ?? []

  // 2. 각 워크플로우의 최근 실행 기록 병렬 조회
  const runResults = await Promise.all(
    workflows.map(async (wf) => {
      const runsRes = await fetch(
        `https://api.github.com/repos/${repo}/actions/workflows/${wf.id}/runs?per_page=5`,
        { headers }
      )
      if (!runsRes.ok) {
        return { workflow: wf, runs: [] as WorkflowRun[], error: `${runsRes.status}` }
      }
      const runsData = await runsRes.json() as { workflow_runs: WorkflowRun[] }
      return { workflow: wf, runs: runsData.workflow_runs ?? [], error: null }
    })
  )

  const result = runResults.map(({ workflow, runs, error }) => {
    const lastRun = runs[0] ?? null
    return {
      id: workflow.id,
      name: workflow.name,
      path: workflow.path,
      state: workflow.state,
      workflow_url: workflow.html_url,
      last_run: lastRun
        ? {
            id: lastRun.id,
            run_number: lastRun.run_number,
            status: lastRun.status,          // queued | in_progress | completed
            conclusion: lastRun.conclusion,  // success | failure | cancelled | skipped | null
            event: lastRun.event,            // schedule | workflow_dispatch | push
            created_at: lastRun.created_at,
            updated_at: lastRun.updated_at,
            run_url: lastRun.html_url,
          }
        : null,
      recent_runs: runs.slice(0, 5).map(r => ({
        id: r.id,
        run_number: r.run_number,
        status: r.status,
        conclusion: r.conclusion,
        event: r.event,
        created_at: r.created_at,
        updated_at: r.updated_at,
      })),
      fetch_error: error,
    }
  })

  // 마지막 성공 실행 기준 최신 업데이트 시각
  const lastSuccessAt = result
    .flatMap(w => w.recent_runs)
    .filter(r => r.conclusion === 'success')
    .map(r => r.updated_at)
    .sort()
    .reverse()[0] ?? null

  return Response.json({
    repo,
    fetched_at: new Date().toISOString(),
    last_success_at: lastSuccessAt,
    workflows: result,
  })
}
