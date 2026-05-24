'use client'
export const runtime = 'edge'

import { useQuery } from '@tanstack/react-query'

interface EvaluationRun {
  id: string
  run_at: string
  run_kind: string
  git_commit: string | null
  params: Record<string, unknown> | null
  n_matches_window: number | null
  n_library_stocks: number | null
  window_days: number | null
  diagnostics: Diagnostics | null
  forward_returns: ForwardReturns | null
  calibration: Calibration | null
  library_recall: LibraryRecall | null
  summary: Summary | null
  notes: string | null
}

interface Diagnostics {
  n_matches: number
  window_days: number
  category_distribution: Record<string, number>
  category_entropy_ratio: number
  body_coverage_pct: number
  library_overlap_rate: number
  llm_verdict_distribution: Record<string, number>
  confidence_stats_per_verdict: Record<string, { n: number; mean: number; p25: number; p50: number; p75: number }>
  category_verdict_breakdown: Record<string, Record<string, number>>
}

interface ForwardReturns {
  horizons_days: number[]
  n_matches_analyzed: number
  n_with_baseline_price: number
  by_verdict: Record<string, Record<string, { n: number; mean_pct?: number; median_pct?: number; hit_2x_rate?: number }>>
  by_category: Record<string, Record<string, { n: number; mean_pct?: number; hit_2x_rate?: number }>>
}

interface Calibration {
  n_labeled: number
  brier_score?: number
  expected_calibration_error?: number
  spearman_corr_conf_vs_confirm?: number | null
  calibration_buckets?: Array<{ bin: string; n: number; actual_confirm_score_mean: number; expected_confirm_score: number; gap: number }>
  note?: string
}

interface LibraryRecall {
  n_library_stocks: number
  lookback_days: number[]
  by_lookback: Array<{ lookback_days: number; n_tested: number; n_hit: number; recall: number | null; mean_confidence: number | null }>
}

interface Summary {
  overall_health: 'green' | 'yellow' | 'red'
  issues: string[]
  key_metrics: Record<string, number | null>
  n_matches_window: number
}

interface EvaluationResponse {
  runs: EvaluationRun[]
  count: number
}

const HEALTH_COLOR: Record<string, string> = {
  green: '#10b981',
  yellow: '#f59e0b',
  red: '#ef4444',
}

function Card(props: { title: string; children: React.ReactNode; subtitle?: string }) {
  return (
    <section
      style={{
        border: '1px solid var(--border)',
        borderRadius: 8,
        padding: 16,
        background: 'var(--bg-card)',
      }}
    >
      <header style={{ marginBottom: 12 }}>
        <h2 style={{ fontSize: 14, fontWeight: 600, margin: 0 }}>{props.title}</h2>
        {props.subtitle && (
          <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '4px 0 0' }}>{props.subtitle}</p>
        )}
      </header>
      {props.children}
    </section>
  )
}

function MetricRow(props: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', fontSize: 13 }}>
      <span style={{ color: 'var(--text-muted)' }}>{props.label}</span>
      <span style={{ fontFamily: props.mono ? 'ui-monospace, monospace' : undefined }}>{props.value}</span>
    </div>
  )
}

function fmtPct(v: number | null | undefined, digits = 1) {
  if (v === null || v === undefined) return '—'
  return `${v.toFixed(digits)}%`
}
function fmtNum(v: number | null | undefined, digits = 3) {
  if (v === null || v === undefined) return '—'
  return v.toFixed(digits)
}

export default function EvaluationPage() {
  const { data, isLoading, error } = useQuery<EvaluationResponse>({
    queryKey: ['evaluation-runs'],
    queryFn: async () => {
      const res = await fetch('/api/evaluation?limit=10')
      if (!res.ok) throw new Error('failed')
      return res.json()
    },
    refetchInterval: 60_000,
  })

  if (isLoading) return <main style={{ padding: 24 }}>Loading…</main>
  if (error) return <main style={{ padding: 24 }}>Error loading evaluation runs</main>
  const runs = data?.runs ?? []
  if (runs.length === 0) {
    return (
      <main style={{ padding: 24 }}>
        <h1>Evaluation</h1>
        <p style={{ color: 'var(--text-muted)' }}>
          평가 run이 없습니다. CLI에서 실행하세요:
        </p>
        <pre style={{ background: 'var(--bg-card)', padding: 12, borderRadius: 6 }}>
          cd apps/collector{'\n'}
          python -m src.hundredx.evaluation.orchestrator --kind full
        </pre>
      </main>
    )
  }

  const latest = runs[0]
  const diag = latest.diagnostics
  const fr = latest.forward_returns
  const cal = latest.calibration
  const recall = latest.library_recall
  const summary = latest.summary

  return (
    <main style={{ padding: 24, maxWidth: 1200, margin: '0 auto' }}>
      <header style={{ marginBottom: 24 }}>
        <h1 style={{ margin: 0 }}>HundredX Evaluation</h1>
        <p style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 4 }}>
          매칭 파이프라인 정확도·캘리브레이션·recall 측정. 최근 {runs.length}개 run.
        </p>
      </header>

      {/* ── Top-line summary ── */}
      <section
        style={{
          border: '1px solid var(--border)',
          borderRadius: 8,
          padding: 20,
          marginBottom: 24,
          background: 'var(--bg-card)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
          <span
            style={{
              display: 'inline-block',
              width: 12,
              height: 12,
              borderRadius: '50%',
              background: HEALTH_COLOR[summary?.overall_health ?? 'yellow'],
            }}
          />
          <strong style={{ fontSize: 18 }}>Health: {summary?.overall_health ?? 'unknown'}</strong>
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            run_kind={latest.run_kind} · {new Date(latest.run_at).toLocaleString()}
            {latest.git_commit && ` · git ${latest.git_commit}`}
          </span>
        </div>
        {summary?.issues && summary.issues.length > 0 && (
          <ul style={{ marginTop: 0, paddingLeft: 20, fontSize: 13 }}>
            {summary.issues.map((issue, i) => (
              <li key={i} style={{ color: '#b45309', marginBottom: 4 }}>{issue}</li>
            ))}
          </ul>
        )}
        {summary?.key_metrics && Object.keys(summary.key_metrics).length > 0 && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 8, marginTop: 12 }}>
            {Object.entries(summary.key_metrics).map(([k, v]) => (
              <div key={k} style={{ padding: 8, background: 'var(--bg)', borderRadius: 6 }}>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{k}</div>
                <div style={{ fontSize: 16, fontWeight: 600, fontFamily: 'ui-monospace, monospace' }}>
                  {typeof v === 'number' ? v.toFixed(3) : String(v)}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: 16 }}>
        {/* Diagnostics */}
        {diag && (
          <Card title="A · Diagnostics" subtitle={`최근 ${diag.window_days}일 · ${diag.n_matches} matches`}>
            <MetricRow label="카테고리 분포 균형도" value={fmtNum(diag.category_entropy_ratio)} mono />
            <MetricRow label="공시 본문 검증가능률" value={fmtPct(diag.body_coverage_pct)} mono />
            <MetricRow label="라이브러리 overlap" value={fmtPct(diag.library_overlap_rate * 100)} mono />
            <div style={{ marginTop: 12, fontSize: 12 }}>
              <div style={{ color: 'var(--text-muted)', marginBottom: 4 }}>카테고리별 매치 수</div>
              {Object.entries(diag.category_distribution)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 10)
                .map(([cat, n]) => (
                  <div key={cat} style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>{cat}</span>
                    <span style={{ fontFamily: 'ui-monospace, monospace' }}>{n}</span>
                  </div>
                ))}
            </div>
            <div style={{ marginTop: 12, fontSize: 12 }}>
              <div style={{ color: 'var(--text-muted)', marginBottom: 4 }}>LLM verdict 분포</div>
              {Object.entries(diag.llm_verdict_distribution).map(([v, n]) => (
                <div key={v} style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>{v}</span>
                  <span style={{ fontFamily: 'ui-monospace, monospace' }}>{n}</span>
                </div>
              ))}
            </div>
          </Card>
        )}

        {/* Forward returns */}
        {fr && (
          <Card title="B · Forward returns" subtitle={`${fr.n_with_baseline_price}/${fr.n_matches_analyzed} matches with baseline price`}>
            {Object.entries(fr.by_verdict).map(([verdict, horizons]) => (
              <div key={verdict} style={{ marginBottom: 8 }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)' }}>{verdict}</div>
                {fr.horizons_days.map((h) => {
                  const d = horizons[`${h}d`] || ({} as { n?: number; mean_pct?: number; hit_2x_rate?: number })
                  if (!d.n) return null
                  return (
                    <div key={h} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
                      <span>{h}d (n={d.n})</span>
                      <span style={{ fontFamily: 'ui-monospace, monospace' }}>
                        avg {fmtPct(d.mean_pct, 1)} · 2x {fmtPct((d.hit_2x_rate ?? 0) * 100, 0)}
                      </span>
                    </div>
                  )
                })}
              </div>
            ))}
          </Card>
        )}

        {/* Calibration */}
        {cal && (
          <Card title="C · Calibration" subtitle={cal.note ?? `${cal.n_labeled} labeled matches`}>
            {cal.n_labeled === 0 ? (
              <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>
                LLM verdict 기록된 매치 없음. /verify-stocks 실행 후 재평가.
              </p>
            ) : (
              <>
                <MetricRow label="Brier score (낮을수록 좋음)" value={fmtNum(cal.brier_score, 4)} mono />
                <MetricRow label="ECE (Expected Calibration Error)" value={fmtNum(cal.expected_calibration_error, 4)} mono />
                <MetricRow label="Spearman (conf vs verdict)" value={fmtNum(cal.spearman_corr_conf_vs_confirm, 3)} mono />
                <div style={{ marginTop: 8, fontSize: 12 }}>
                  <div style={{ color: 'var(--text-muted)', marginBottom: 4 }}>Confidence 버킷별 실제 confirm rate</div>
                  {cal.calibration_buckets?.map((b) => (
                    <div key={b.bin} style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span>{b.bin} (n={b.n})</span>
                      <span style={{ fontFamily: 'ui-monospace, monospace' }}>
                        actual {b.actual_confirm_score_mean.toFixed(2)} · gap {b.gap > 0 ? '+' : ''}{b.gap.toFixed(2)}
                      </span>
                    </div>
                  ))}
                </div>
              </>
            )}
          </Card>
        )}

        {/* Library recall */}
        {recall && (
          <Card title="D · Library recall (point-in-time)" subtitle={`${recall.n_library_stocks} library stocks tested`}>
            {recall.by_lookback.map((b) => (
              <div key={b.lookback_days} style={{ marginBottom: 4 }}>
                <MetricRow
                  label={`${b.lookback_days}일 전 사전탐지`}
                  value={
                    b.recall === null ? '—' : (
                      <>
                        <span style={{ fontFamily: 'ui-monospace, monospace' }}>
                          {b.n_hit}/{b.n_tested} ({(b.recall * 100).toFixed(0)}%)
                        </span>
                        {b.mean_confidence !== null && (
                          <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 8 }}>
                            avg conf {b.mean_confidence.toFixed(2)}
                          </span>
                        )}
                      </>
                    )
                  }
                />
              </div>
            ))}
            <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 8 }}>
              라이브러리 100배 종목 각각에 대해 rise_start_date 이전 N일 시점으로 scanner를 되돌려 매칭 여부 측정.
            </p>
          </Card>
        )}
      </div>

      {/* History */}
      <section style={{ marginTop: 24 }}>
        <h2 style={{ fontSize: 16, marginBottom: 12 }}>최근 평가 이력</h2>
        <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border)' }}>
              <th style={{ textAlign: 'left', padding: 6 }}>실행시각</th>
              <th style={{ textAlign: 'left', padding: 6 }}>kind</th>
              <th style={{ textAlign: 'left', padding: 6 }}>health</th>
              <th style={{ textAlign: 'right', padding: 6 }}>matches</th>
              <th style={{ textAlign: 'right', padding: 6 }}>library</th>
              <th style={{ textAlign: 'left', padding: 6 }}>git</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((r) => (
              <tr key={r.id} style={{ borderBottom: '1px solid var(--border)' }}>
                <td style={{ padding: 6 }}>{new Date(r.run_at).toLocaleString()}</td>
                <td style={{ padding: 6 }}>{r.run_kind}</td>
                <td style={{ padding: 6 }}>
                  <span
                    style={{
                      display: 'inline-block',
                      width: 8,
                      height: 8,
                      borderRadius: '50%',
                      background: HEALTH_COLOR[(r.summary?.overall_health ?? 'yellow') as string],
                      marginRight: 6,
                    }}
                  />
                  {r.summary?.overall_health ?? '—'}
                </td>
                <td style={{ padding: 6, textAlign: 'right', fontFamily: 'ui-monospace, monospace' }}>
                  {r.n_matches_window ?? '—'}
                </td>
                <td style={{ padding: 6, textAlign: 'right', fontFamily: 'ui-monospace, monospace' }}>
                  {r.n_library_stocks ?? '—'}
                </td>
                <td style={{ padding: 6, fontFamily: 'ui-monospace, monospace' }}>{r.git_commit ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </main>
  )
}
