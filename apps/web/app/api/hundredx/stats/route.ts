export const runtime = 'edge'

import { createServerClient } from '@/lib/supabase'

type LibRow = {
  ticker: string
  category: string
  earliest_signal_date: string | null
  rise_start_date: string | null
  peak_multiplier: number | null
}

type MatchRow = {
  ticker: string
  category: string
  confidence: number
  fingerprint_score: number | null
  exited_at: string | null
  first_detected_at: string | null
}

function monthsBetween(a: string | null, b: string | null): number | null {
  if (!a || !b) return null
  const da = new Date(a), db = new Date(b)
  const diff = (db.getTime() - da.getTime()) / (1000 * 60 * 60 * 24 * 30.5)
  return Math.round(diff * 10) / 10
}

function avg(vals: number[]): number | null {
  if (!vals.length) return null
  return Math.round((vals.reduce((s, v) => s + v, 0) / vals.length) * 10) / 10
}

const CATEGORIES = [
  '수주잔고_선행',
  '수익성_급전환',
  '빅테크_파트너',
  '플랫폼_독점',
  '정책_수혜',
  '공급_병목',
  '임상_파이프라인',
]

export async function GET() {
  const supabase = createServerClient()

  const [libRes, matchRes, stockCountRes] = await Promise.all([
    supabase.from('hundredx_library_stocks')
      .select('ticker, category, earliest_signal_date, rise_start_date, peak_multiplier'),
    supabase.from('hundredx_category_matches')
      .select('ticker, category, confidence, fingerprint_score, exited_at, first_detected_at'),
    supabase.from('stocks').select('ticker', { count: 'exact', head: true }).eq('is_active', true),
  ])

  if (libRes.error) return Response.json({ error: libRes.error.message }, { status: 500 })

  const libRows = (libRes.data ?? []) as LibRow[]
  const matchRows = (matchRes.data ?? []) as MatchRow[]
  const totalActive = stockCountRes.count ?? 0

  // Active matches only
  const activeMatches = matchRows.filter(m => !m.exited_at)

  // Per-category stats
  const by_category = CATEGORIES.map(cat => {
    const libCat = libRows.filter(r => r.category === cat)
    const peaks = libCat.map(r => r.peak_multiplier).filter((v): v is number => v != null)
    const leadMonths = libCat
      .map(r => monthsBetween(r.earliest_signal_date, r.rise_start_date))
      .filter((v): v is number => v != null && v > 0)

    const activeCat = activeMatches.filter(m => m.category === cat)
    const confs = activeCat.map(m => m.confidence)
    const fpCount = activeCat.filter(m => m.fingerprint_score != null).length

    // Exits in last 30 days
    const cutoff30d = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString()
    const exits30d = matchRows.filter(
      m => m.category === cat && m.exited_at && m.exited_at >= cutoff30d
    ).length

    return {
      category: cat,
      // Library ground truth
      library_count: libCat.length,
      library_peak_min: peaks.length ? Math.min(...peaks) : null,
      library_peak_max: peaks.length ? Math.max(...peaks) : null,
      library_peak_avg: avg(peaks),
      library_lead_months_avg: avg(leadMonths),
      // Current scanner output
      active_matches: activeCat.length,
      avg_confidence: avg(confs),
      fingerprint_matches: fpCount,
      exits_30d: exits30d,
    }
  })

  const totalLibraryStocks = [...new Set(libRows.map(r => r.ticker))].length

  return Response.json({
    by_category,
    summary: {
      total_active: activeMatches.length,
      total_library_stocks: totalLibraryStocks,
      scan_coverage: totalActive,
      categories_firing: by_category.filter(c => c.active_matches > 0).length,
    },
  })
}
