export const runtime = 'edge'

import { createServerClient } from '@/lib/supabase'

export async function GET() {
  const supabase = createServerClient()
  const { count } = await supabase
    .from('screen_scores')
    .select('*', { count: 'exact', head: true })

  return Response.json({ hasData: (count ?? 0) > 0 })
}
