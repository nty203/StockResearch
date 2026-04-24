export const runtime = 'edge'

import { createServerClient } from '@/lib/supabase'

export async function GET() {
  const supabase = createServerClient()
  const { data, error } = await supabase
    .from('watchlist')
    .select('status')
    .returns<{ status: string }[]>()

  if (error) return Response.json({ error: error.message }, { status: 500 })

  const counts = { green: 0, yellow: 0, candidate: 0 }
  for (const row of data ?? []) {
    const s = row.status as keyof typeof counts
    if (s in counts) counts[s]++
  }
  return Response.json(counts)
}
