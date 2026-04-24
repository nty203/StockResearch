export const runtime = 'edge'

import { createServerClient } from '@/lib/supabase'

export async function POST(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  const supabase = createServerClient()

  const { error } = await supabase
    .from('analysis_queue')
    .update({ status: 'PENDING' as const, claimed_at: null, claimed_by: null })
    .eq('id', id)

  if (error) return Response.json({ error: error.message }, { status: 500 })
  return Response.json({ ok: true })
}
