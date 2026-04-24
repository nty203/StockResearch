export const runtime = 'edge'

import { createServerClient } from '@/lib/supabase'

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url)
  const limit = Math.min(Number(searchParams.get('limit') ?? 30), 100)

  const supabase = createServerClient()
  const today = new Date().toISOString().slice(0, 10)

  const { data, error } = await supabase
    .from('screen_scores')
    .select('*')
    .eq('run_date', today)
    .order('score_10x', { ascending: false })
    .limit(limit)

  if (error) return Response.json({ error: error.message }, { status: 500 })
  return Response.json(data)
}
