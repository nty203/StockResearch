export const runtime = 'edge'

import { createServerClient } from '@/lib/supabase'
import type { WatchlistStatus } from '@stock/shared'

export async function PATCH(req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  const raw = await req.json() as {
    status?: string
    notes?: string
    target_price?: number
    stop_loss?: number
    position_size_plan?: string
  }

  const supabase = createServerClient()
  const { data, error } = await supabase
    .from('watchlist')
    .update({
      ...(raw.status !== undefined && { status: raw.status as WatchlistStatus }),
      ...(raw.notes !== undefined && { notes: raw.notes }),
      ...(raw.target_price !== undefined && { target_price: raw.target_price }),
      ...(raw.stop_loss !== undefined && { stop_loss: raw.stop_loss }),
      ...(raw.position_size_plan !== undefined && { position_size_plan: raw.position_size_plan }),
    })
    .eq('id', id)
    .select()
    .single()

  if (error) return Response.json({ error: error.message }, { status: 500 })
  return Response.json(data)
}

export async function DELETE(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  const supabase = createServerClient()
  const { error } = await supabase.from('watchlist').delete().eq('id', id)
  if (error) return Response.json({ error: error.message }, { status: 500 })
  return new Response(null, { status: 204 })
}
