export const runtime = 'edge'

import { createServerClient } from '@/lib/supabase'
import type { MacroIdea } from '@stock/shared'

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const limit = Math.min(parseInt(searchParams.get('limit') ?? '50'), 100)
  const offset = parseInt(searchParams.get('offset') ?? '0')
  const date = searchParams.get('date')

  const supabase = createServerClient()

  let query = supabase
    .from('macro_ideas')
    .select('*', { count: 'exact' })
    .order('total_score', { ascending: false })

  if (date) {
    query = query.eq('date', date)
  } else {
    query = query.order('date', { ascending: false })
  }

  const { data, error, count } = await query.range(offset, offset + limit - 1)

  if (error) {
    return Response.json({ error: error.message }, { status: 500 })
  }

  return Response.json({
    ideas: (data ?? []) as MacroIdea[],
    count: count ?? 0,
  })
}
