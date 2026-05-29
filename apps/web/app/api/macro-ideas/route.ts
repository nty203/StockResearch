export const runtime = 'edge'

import { createServerClient } from '@/lib/supabase'
import type { MacroIdea } from '@stock/shared'

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const limit = Math.min(parseInt(searchParams.get('limit') ?? '20'), 50)
  const offset = parseInt(searchParams.get('offset') ?? '0')

  const supabase = createServerClient()

  const { data, error, count } = await supabase
    .from('macro_ideas')
    .select('*', { count: 'exact' })
    .order('date', { ascending: false })
    .order('total_score', { ascending: false })
    .range(offset, offset + limit - 1)

  if (error) {
    return Response.json({ error: error.message }, { status: 500 })
  }

  return Response.json({
    ideas: (data ?? []) as MacroIdea[],
    count: count ?? 0,
  })
}
