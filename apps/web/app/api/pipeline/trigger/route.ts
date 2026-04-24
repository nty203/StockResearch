export const runtime = 'edge'

export async function POST(req: Request) {
  const { workflow } = await req.json() as { workflow: string }

  const GITHUB_PAT  = process.env.GITHUB_PAT
  const GITHUB_REPO = process.env.GITHUB_REPO
  if (!GITHUB_PAT || !GITHUB_REPO) {
    return Response.json({ error: 'GitHub credentials not configured' }, { status: 500 })
  }

  const res = await fetch(
    `https://api.github.com/repos/${GITHUB_REPO}/actions/workflows/${workflow}/dispatches`,
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
