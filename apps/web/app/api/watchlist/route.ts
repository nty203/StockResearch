export const runtime = 'edge'

import { createServerClient } from '@/lib/supabase'
import type { WatchlistStatus } from '@stock/shared'

export async function GET(req: Request) {
  const url = new URL(req.url)
  const status = (url.searchParams.get('status') ?? 'green') as WatchlistStatus

  const supabase = createServerClient()
  const { data, error } = await supabase
    .from('watchlist')
    .select('*')
    .eq('status', status)
    .order('added_at', { ascending: false })

  if (error) return Response.json({ error: error.message }, { status: 500 })
  return Response.json(data)
}

export async function POST(req: Request) {
  const body = await req.json() as {
    ticker: string
    status?: string
    notes?: string
    target_price?: number
    stop_loss?: number
    position_size_plan?: string
  }

  const supabase = createServerClient()
  const { data, error } = await supabase
    .from('watchlist')
    .insert({
      ticker: body.ticker,
      status: (body.status ?? 'candidate') as WatchlistStatus,
      notes: body.notes ?? null,
      target_price: body.target_price ?? null,
      stop_loss: body.stop_loss ?? null,
      position_size_plan: body.position_size_plan ?? null,
    })
    .select()
    .single()

  if (error) return Response.json({ error: error.message }, { status: 500 })
  return Response.json(data, { status: 201 })
}
