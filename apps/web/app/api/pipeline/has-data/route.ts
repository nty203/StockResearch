export const runtime = 'edge'

import { createServerClient } from '@/lib/supabase'

export async function GET() {
  const supabase = createServerClient()
  const { count } = await supabase
    .from('pipeline_runs')
    .select('*', { count: 'exact', head: true })
    .eq('status', 'success')

  return Response.json({ hasData: (count ?? 0) > 0 })
}
