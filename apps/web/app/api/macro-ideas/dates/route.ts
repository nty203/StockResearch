export const runtime = 'edge'

import { createServerClient } from '@/lib/supabase'

export async function GET() {
  const supabase = createServerClient()

  // Use DB-side GROUP BY via RPC — avoids fetching all rows just to deduplicate
  const { data, error } = await supabase.rpc('get_macro_idea_dates')

  if (error) {
    // Fallback: fetch date column with a cap and deduplicate in JS
    const { data: rows, error: fallbackError } = await supabase
      .from('macro_ideas')
      .select('date')
      .order('date', { ascending: false })
      .limit(1000)

    if (fallbackError) {
      return Response.json({ error: fallbackError.message }, { status: 500 })
    }

    const countByDate = new Map<string, number>()
    for (const row of rows ?? []) {
      countByDate.set(row.date, (countByDate.get(row.date) ?? 0) + 1)
    }
    const dates = Array.from(countByDate.entries()).map(([date, count]) => ({ date, count }))
    return Response.json({ dates })
  }

  return Response.json({ dates: data ?? [] })
}
