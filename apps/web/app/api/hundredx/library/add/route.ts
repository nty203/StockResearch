export const runtime = 'edge'

import { createServerClient } from '@/lib/supabase'
import type { RiseCategory } from '@stock/shared'

const VALID_CATEGORIES = [
  '수주잔고_선행', '수익성_급전환', '빅테크_파트너',
  '플랫폼_독점', '정책_수혜', '공급_병목', '임상_파이프라인',
]

export async function POST(req: Request) {
  let body: Record<string, unknown>
  try {
    body = await req.json()
  } catch {
    return Response.json({ error: 'invalid JSON' }, { status: 400 })
  }

  const { ticker, category, rise_start_date, earliest_signal_date, peak_multiplier, notes } = body as {
    ticker?: string
    category?: string
    rise_start_date?: string
    earliest_signal_date?: string
    peak_multiplier?: number
    notes?: string
  }

  if (!ticker || typeof ticker !== 'string') return Response.json({ error: 'ticker required' }, { status: 400 })
  if (!category || !VALID_CATEGORIES.includes(category)) return Response.json({ error: 'invalid category' }, { status: 400 })

  const supabase = createServerClient()

  // Validate ticker exists
  const { data: stock } = await supabase.from('stocks').select('ticker').eq('ticker', ticker).maybeSingle()
  if (!stock) return Response.json({ error: `ticker ${ticker} not found in stocks table` }, { status: 422 })

  const { error } = await supabase.from('hundredx_library_stocks').upsert({
    ticker,
    category: category as RiseCategory,
    rise_start_date: rise_start_date || null,
    earliest_signal_date: earliest_signal_date || null,
    peak_multiplier: peak_multiplier ?? null,
    notes: notes || null,
    pre_rise_signals: null,
    latest_multiplier: null,
    price_at_rise_start: null,
    latest_updated_at: null,
  }, { onConflict: 'ticker,category' })

  if (error) return Response.json({ error: error.message }, { status: 500 })
  return Response.json({ ok: true, ticker, category })
}

export async function DELETE(req: Request) {
  const { searchParams } = new URL(req.url)
  const ticker = searchParams.get('ticker')
  const category = searchParams.get('category')
  if (!ticker || !category) return Response.json({ error: 'ticker and category required' }, { status: 400 })

  const supabase = createServerClient()
  const { error } = await supabase.from('hundredx_library_stocks')
    .delete().eq('ticker', ticker).eq('category', category as RiseCategory)
  if (error) return Response.json({ error: error.message }, { status: 500 })
  return Response.json({ ok: true })
}
