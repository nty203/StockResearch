export const runtime = 'edge'

import { createServerClient } from '@/lib/supabase'

type Match = {
  ticker: string
  category: string
  confidence: number
  evidence: Array<{ source_type: string; source_id: string; text_excerpt: string; date: string | null; amount: number | null }> | null
  first_detected_at: string | null
  detected_at: string
  exited_at: string | null
  analog_ticker: string | null
  analog_date: string | null
  analog_multiplier: number | null
  fingerprint_score: number | null
  fingerprint_dims: { matched: string[]; missing: string[]; details: Record<string, unknown> } | null
  timeline_progress: {
    library_ticker: string
    library_category: string
    library_peak_multiplier: number | null
    fired_triggers: Array<{
      seq: number
      name: string
      months_from_rise: number
      fired_at_date: string | null
      fired_at_months_ago: number | null
      weight: number
      matched_signals: string[]
    }>
    total_triggers: number
    trajectory_score: number
    current_position_months: number
    next_expected: { seq: number; name: string; months_from_rise: number; expected_in_months: number } | null
  } | null
  pptr_match: {
    library_ticker: string
    producer_id: string
    matched_conditions: string[]
  } | null
  price_baseline_date: string | null
  price_baseline_close: number | null
  price_latest_date: string | null
  price_latest_close: number | null
  price_peak_date: string | null
  price_peak_close: number | null
  price_current_multiplier: number | null
  price_change_pct: number | null
  price_peak_multiplier: number | null
  price_peak_change_pct: number | null
  price_performance_updated_at: string | null
}

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url)
  const minConfidence = Math.max(0, Math.min(1, Number(searchParams.get('min_confidence') ?? 0.5)))

  const supabase = createServerClient()

  // Active matches only (exited_at IS NULL), above confidence threshold
  const { data: matches, error } = await supabase
    .from('hundredx_category_matches')
    .select('*')
    .is('exited_at', null)
    .gte('confidence', minConfidence)
    .order('confidence', { ascending: false })

  if (error) return Response.json({ error: error.message }, { status: 500 })

  const rows = (matches ?? []) as unknown as Match[]
  const tickers = [...new Set(rows.map(r => r.ticker))]

  // Join: stock metadata
  const stocksRes = tickers.length > 0
    ? await supabase.from('stocks').select('ticker, name_kr, name_en, market, sector_tag').in('ticker', tickers)
    : { data: [] as { ticker: string; name_kr: string | null; name_en: string | null; market: string | null; sector_tag: string | null }[] }

  type Stock = { ticker: string; name_kr: string | null; name_en: string | null; market: string | null; sector_tag: string | null }
  const stockMap: Record<string, Stock> = Object.fromEntries(((stocksRes.data as Stock[] | null) ?? []).map(s => [s.ticker, s]))

  // Group by ticker
  const byTicker: Record<string, Match[]> = {}
  for (const m of rows) {
    if (!byTicker[m.ticker]) byTicker[m.ticker] = []
    byTicker[m.ticker].push(m)
  }

  const result = Object.entries(byTicker).map(([ticker, cats]) => {
    // ── Conviction formula (max = 100) ────────────────────────────────────────
    // 1. Fingerprint bonus (0–40): library pattern match is the strongest signal.
    //    Requires ≥0.30 to contribute — below that the match is noise.
    const bestFP = Math.max(0, ...cats.map(c => c.fingerprint_score ?? 0))
    const fpBonus = bestFP >= 0.30 ? Math.round(bestFP * 40 * 10) / 10 : 0

    // 2. Confidence depth (0–40): average rule-based detector confidence.
    //    Uses raw confidence (not fingerprint) so the two signals are independent.
    const avgConf = cats.reduce((s, c) => s + c.confidence, 0) / cats.length
    const confScore = Math.round(avgConf * 40 * 10) / 10

    // 3. Breadth (0–15): multiple category matches mean different dimensions agree.
    //    Caps at 3 categories to avoid inflation from correlated categories.
    const breadthScore = Math.round(Math.min(15, (cats.length / 3) * 15) * 10) / 10

    // 4. Timeline progress bonus (0–5): fired ≥1 trigger stage in library timeline.
    const bestTimeline = cats.reduce(
      (best, c) => Math.max(best, c.timeline_progress?.trajectory_score ?? 0), 0
    )
    const timelineBonus = bestTimeline >= 0.25 ? Math.round(bestTimeline * 5 * 10) / 10 : 0

    const conviction = fpBonus + confScore + breadthScore + timelineBonus
    const hasPptrMatch = cats.some(c => c.pptr_match)

    // ── Quality grade ─────────────────────────────────────────────────────────
    // S: PPTR full match + library fingerprint ≥0.65 AND conviction ≥65
    // A: PPTR full match + fingerprint ≥0.45 OR conviction ≥55
    // B: non-PPTR/fingerprint candidate, still below A-grade quality gate
    // C: passes min_confidence threshold (baseline)
    let grade: 'S' | 'A' | 'B' | 'C'
    if (hasPptrMatch && bestFP >= 0.65 && conviction >= 65) grade = 'S'
    else if (hasPptrMatch && (bestFP >= 0.45 || conviction >= 55)) grade = 'A'
    else if (bestFP >= 0.25 || conviction >= 40) grade = 'B'
    else grade = 'C'

    // First-signal date = oldest first_detected_at across categories
    const firstSignal = cats
      .map(c => c.first_detected_at)
      .filter((d): d is string => !!d)
      .sort()[0] ?? null

    const priceRow = cats.find(c => c.price_current_multiplier != null || c.price_change_pct != null) ?? null

    return {
      ticker,
      stock: stockMap[ticker] ?? null,
      conviction: Math.round(conviction * 10) / 10,
      grade,
      best_fingerprint_score: bestFP > 0 ? Math.round(bestFP * 1000) / 1000 : null,
      first_signal_at: firstSignal,
      price_performance: priceRow ? {
        baseline_date: priceRow.price_baseline_date,
        baseline_close: priceRow.price_baseline_close,
        latest_date: priceRow.price_latest_date,
        latest_close: priceRow.price_latest_close,
        peak_date: priceRow.price_peak_date,
        peak_close: priceRow.price_peak_close,
        current_multiplier: priceRow.price_current_multiplier,
        change_pct: priceRow.price_change_pct,
        peak_multiplier: priceRow.price_peak_multiplier,
        peak_change_pct: priceRow.price_peak_change_pct,
        updated_at: priceRow.price_performance_updated_at,
      } : null,
      categories: cats.map(c => ({
        category: c.category,
        confidence: c.confidence,
        evidence: c.evidence ?? [],
        first_detected_at: c.first_detected_at,
        detected_at: c.detected_at,
        analog: c.analog_ticker ? {
          ticker: c.analog_ticker,
          date: c.analog_date,
          multiplier: c.analog_multiplier,
        } : null,
        fingerprint: c.fingerprint_score != null ? {
          score: c.fingerprint_score,
          matched: c.fingerprint_dims?.matched ?? [],
          missing: c.fingerprint_dims?.missing ?? [],
          details: c.fingerprint_dims?.details ?? {},
        } : null,
        timeline: c.timeline_progress ?? null,
        pptr: c.pptr_match ?? null,
      })).sort((a, b) => (b.fingerprint?.score ?? b.confidence) - (a.fingerprint?.score ?? a.confidence)),
    }
  })

  // Sort: grade weight first (S→A→B→C), then conviction descending
  const gradeOrder: Record<string, number> = { S: 0, A: 1, B: 2, C: 3 }
  result.sort((a, b) => {
    const gd = gradeOrder[a.grade] - gradeOrder[b.grade]
    return gd !== 0 ? gd : b.conviction - a.conviction
  })

  return Response.json({
    results: result,
    count: result.length,
    grade_counts: {
      S: result.filter(r => r.grade === 'S').length,
      A: result.filter(r => r.grade === 'A').length,
      B: result.filter(r => r.grade === 'B').length,
      C: result.filter(r => r.grade === 'C').length,
    },
  })
}
