export const runtime = 'edge'

import { createServerClient } from '@/lib/supabase'

export async function GET() {
  const supabase = createServerClient()

  const { data, error } = await supabase
    .from('analysis_queue')
    .select('*')
    .order('created_at', { ascending: false })
    .limit(100)

  if (error) return Response.json({ error: error.message }, { status: 500 })

  const pending = (data ?? []).filter(r => r.status === 'PENDING')
  const claimed = (data ?? []).filter(r => r.status === 'CLAIMED')
  const completed = (data ?? []).filter(r => r.status === 'COMPLETED' || r.status === 'FAILED' || r.status === 'INVALID')

  return Response.json({ pending, claimed, completed })
}
