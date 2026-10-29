import type { ChartProps, CitationT } from '../catalog/schemas'

/** A number shown in a stat tile or the headline, derived only from a chart's verified points. */
export interface Stat {
  kind: 'gap' | 'value'
  label: string // category, e.g. "540B"
  value: number
  decimals: number
  from?: number // gap: the first series' value
  to?: number // gap: the last series' value
  citation: CitationT
}

const decimalsOf = (n: number) => (Number.isInteger(n) ? 0 : (String(n).split('.')[1] ?? '').length)
const round = (n: number, d: number) => Number(n.toFixed(d))

/**
 * Two series sharing categories -> the gap (last series minus first) per category.
 * One series -> the values themselves (up to 4: all of them, or first / peak / last).
 * The model never computes these: the UI does, from values the server has already verified.
 */
export function chartStats(c: ChartProps): Stat[] {
  if (c.series.length === 2) {
    const [base, top] = c.series
    return top.points.flatMap((p) => {
      const b = base.points.find((x) => x.label === p.label)
      if (!b) return []
      const d = Math.max(decimalsOf(p.value), decimalsOf(b.value))
      return [{ kind: 'gap' as const, label: p.label, value: round(p.value - b.value, d), decimals: d, from: b.value, to: p.value, citation: p.citation }]
    }).slice(0, 4)
  }
  const pts = c.series[0]?.points ?? []
  const pick =
    pts.length <= 4
      ? pts
      : [...new Set([pts[0], pts.reduce((m, p) => (p.value > m.value ? p : m)), pts[pts.length - 1]])]
  return pick.map((p) => ({ kind: 'value' as const, label: p.label, value: p.value, decimals: decimalsOf(p.value), citation: p.citation }))
}

/** The headline number: the largest gap, or the peak value. */
export function keyStat(c: ChartProps): Stat | null {
  const stats = chartStats(c)
  if (!stats.length) return null
  return stats.reduce((m, s) => (Math.abs(s.value) > Math.abs(m.value) ? s : m))
}
