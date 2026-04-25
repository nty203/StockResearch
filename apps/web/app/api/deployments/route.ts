export const runtime = 'edge'

/**
 * GET /api/deployments
 * Cloudflare Pages 최신 배포 상태 조회
 *
 * 필요한 환경변수:
 *   CF_API_TOKEN   — Cloudflare API 토큰 (Account: Cloudflare Pages:Read)
 *   CF_ACCOUNT_ID  — Cloudflare Account ID (dash.cloudflare.com URL에서 확인)
 *   CF_PROJECT_NAME — Cloudflare Pages 프로젝트명 (기본값: stockresearch)
 */
export async function GET() {
  const token = process.env.CF_API_TOKEN
  const accountId = process.env.CF_ACCOUNT_ID
  const projectName = process.env.CF_PROJECT_NAME ?? 'stockresearch'

  if (!token || !accountId) {
    return Response.json(
      { error: 'CF_API_TOKEN or CF_ACCOUNT_ID not configured' },
      { status: 503 },
    )
  }

  try {
    const res = await fetch(
      `https://api.cloudflare.com/client/v4/accounts/${accountId}/pages/projects/${projectName}/deployments?per_page=5`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      },
    )

    if (!res.ok) {
      const body = await res.text()
      return Response.json({ error: `CF API error: ${body}` }, { status: res.status })
    }

    const data = await res.json() as {
      result: Array<{
        id: string
        url: string
        created_on: string
        latest_stage: { name: string; status: string }
        deployment_trigger: { metadata: { commit_message: string; commit_hash: string } }
        environment: string
      }>
    }

    const deployments = (data.result ?? []).map(d => ({
      id: d.id,
      url: d.url,
      created_on: d.created_on,
      status: d.latest_stage?.status ?? 'unknown',
      stage: d.latest_stage?.name ?? 'unknown',
      environment: d.environment,
      commit_message: d.deployment_trigger?.metadata?.commit_message ?? '',
      commit_hash: d.deployment_trigger?.metadata?.commit_hash?.slice(0, 7) ?? '',
    }))

    return Response.json({ deployments })
  } catch (err) {
    return Response.json({ error: String(err) }, { status: 500 })
  }
}
