import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ReferenceDot, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { ChartProps } from '../catalog/schemas'
import { useI18n } from '../i18n/context'
import { chartStats, keyStat, type Stat } from '../lib/keyNumbers'
import { stripUrls } from '../lib/text'
import type { Verification } from '../state/useAnswer'
import { Card } from './Card'
import { CitationChip } from './CitationChip'
import { StatNumber } from './StatNumber'

const COLORS = ['var(--color-series-1)', 'var(--color-series-2)']
const FONT = '"IBM Plex Sans Arabic", "Noto Sans Arabic", system-ui, sans-serif'

function StatTiles({ stats, best, unit }: { stats: Stat[]; best: Stat | null; unit: string }) {
  const { t, num } = useI18n()
  return (
    <div data-testid="stat-tiles" className="grid gap-2" style={{ gridTemplateColumns: `repeat(${stats.length}, minmax(0, 1fr))` }}>
      {stats.map((s) => {
        const hot = best?.label === s.label
        return (
          <div key={s.label} data-testid="stat-tile" data-hot={hot} className={`rounded-xl px-3 py-2 ${hot ? 'bg-hot-soft' : 'bg-raised'}`}>
            <div className={`text-xl font-bold leading-tight tabular-nums ${hot ? 'text-hot' : 'text-ink'}`}>
              <StatNumber stat={s} />
              {unit && !(s.kind === 'gap' && unit === '%') ? <span className="ms-0.5 text-sm font-semibold">{unit}</span> : null}
            </div>
            <div className="mt-0.5 flex flex-wrap items-baseline gap-x-1.5 text-xs text-muted">
              <bdi className="font-semibold text-ink">{s.label}</bdi>
              {s.kind === 'gap' && s.from !== undefined && s.to !== undefined ? (
                <bdi className="tabular-nums">{t('key.from', { a: num(s.from), b: num(s.to) })}</bdi>
              ) : null}
            </div>
          </div>
        )
      })}
    </div>
  )
}

export function ChartCard({ props, verification }: { props: ChartProps; verification?: Verification }) {
  const { num, t } = useI18n()
  const rtl = props.lang === 'ar'
  const stats = chartStats(props)
  const best = keyStat(props)
  // Keep the data in logical order and mirror only the display (XAxis reversed in RTL).
  const labels: string[] = []
  for (const s of props.series) for (const p of s.points) if (!labels.includes(p.label)) labels.push(p.label)
  const data = labels.map((label) => {
    const row: Record<string, string | number> = { label }
    props.series.forEach((s, i) => {
      const p = s.points.find((pt) => pt.label === label)
      if (p) row[`s${i}`] = p.value
    })
    return row
  })
  const fmt = (v: number) => `${num(v)}${props.unit}`
  const summary = props.series
    .map((s) => `${s.name}: ${s.points.map((p) => `${p.label} ${fmt(p.value)}`).join(', ')}`)
    .join('; ')
  const last = props.series.length - 1
  const color = (i: number) => COLORS[props.series.length === 1 ? 1 : i]
  // The point the headline talks about: the top series at the key category.
  const peak = best ? props.series[last].points.find((p) => p.label === best.label) : undefined
  const tick = { fontFamily: FONT, fontSize: 12, fill: 'var(--color-muted)' }
  const common = { data, margin: { top: 30, right: 18, bottom: 26, left: 18 } }
  const axes = (
    <>
      <CartesianGrid stroke="var(--color-line)" strokeOpacity={0.7} vertical={false} />
      <XAxis
        dataKey="label"
        reversed={rtl}
        tick={tick}
        tickLine={false}
        axisLine={{ stroke: 'var(--color-line)' }}
        label={{ value: stripUrls(props.x_label), position: 'insideBottom', offset: -18, style: { ...tick, fill: 'var(--color-ink)' } }}
      />
      <YAxis orientation={rtl ? 'right' : 'left'} tick={tick} tickLine={false} axisLine={false} tickFormatter={(v: number) => fmt(v)} width={52} />
      <Tooltip
        formatter={(v) => fmt(Number(v))}
        contentStyle={{ direction: rtl ? 'rtl' : 'ltr', fontFamily: FONT, background: 'var(--color-surface)', border: 'none', borderRadius: 12, boxShadow: 'var(--shadow-float)', color: 'var(--color-ink)' }}
      />
      <Legend align={rtl ? 'right' : 'left'} verticalAlign="top" iconType="circle" wrapperStyle={{ fontFamily: FONT, fontSize: 12, paddingBottom: 6 }} />
      {peak ? (
        <ReferenceDot
          x={peak.label}
          y={peak.value}
          r={8}
          zIndex={1300}
          fill="var(--color-hot)"
          stroke="var(--color-surface)"
          strokeWidth={3}
          label={{
            // At the last category the dot sits on the plot's edge: put the label inward, not above.
            position: peak.label === labels[labels.length - 1] ? (rtl ? 'right' : 'left') : 'top',
            offset: 14,
            value: `${fmt(peak.value)} · ${t('cite.page', { n: peak.citation.page })}`,
            // The chart inherits dir=rtl in Arabic; keep the label's own direction so it grows away from the dot.
            style: { fontFamily: FONT, fontSize: 12, fontWeight: 700, fill: 'var(--color-hot)', direction: 'ltr', unicodeBidi: 'plaintext' },
          }}
        />
      ) : null}
    </>
  )

  return (
    <Card lang={props.lang} type="chart" title={props.title} verification={verification}>
      {stats.length > 1 ? <StatTiles stats={stats} best={best} unit={props.unit} /> : null}
      <div role="img" aria-label={`${props.title}. ${summary}`} data-testid="chart" className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          {props.chart_type === 'bar' ? (
            <BarChart {...common}>
              {axes}
              {props.series.map((s, i) => (
                <Bar key={i} dataKey={`s${i}`} name={stripUrls(s.name)} fill={color(i)} radius={[6, 6, 0, 0]} maxBarSize={36} isAnimationActive={false} />
              ))}
            </BarChart>
          ) : (
            <LineChart {...common}>
              {axes}
              {props.series.map((s, i) => (
                <Line
                  key={i}
                  type="monotone"
                  dataKey={`s${i}`}
                  name={stripUrls(s.name)}
                  stroke={color(i)}
                  strokeWidth={i === last ? 4 : 3}
                  strokeLinecap="round"
                  dot={{ r: 5.5, strokeWidth: 3, fill: 'var(--color-surface)' }}
                  activeDot={{ r: 7 }}
                  isAnimationActive={false}
                />
              ))}
            </LineChart>
          )}
        </ResponsiveContainer>
      </div>
      {/* sr-only on a wrapper: a <table> sizes to its content and ignores width:1px. */}
      <div className="sr-only">
        <table data-testid="chart-data-table">
          <caption>{props.title}</caption>
          <thead>
            <tr>
              <th scope="col">{props.x_label}</th>
              {props.series.map((s, i) => (
                <th key={i} scope="col">
                  {s.name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((row) => (
              <tr key={String(row.label)}>
                <th scope="row">{row.label}</th>
                {props.series.map((_, i) => (
                  <td key={i}>{row[`s${i}`] !== undefined ? fmt(Number(row[`s${i}`])) : ''}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="grid gap-1 text-xs text-muted">
        {props.series.map((s, i) => (
          <p key={i} data-testid="chart-sources" className="m-0 flex flex-wrap items-center gap-1">
            <span className="inline-block h-2 w-2 rounded-full" style={{ background: color(i) }} aria-hidden />
            <bdi className="me-1">{stripUrls(s.name)}</bdi>
            {s.points.map((p, j) => (
              <span key={j} data-testid="chart-point">
                <CitationChip citation={p.citation} label={`${p.label} ${fmt(p.value)}`} />
              </span>
            ))}
          </p>
        ))}
      </div>
    </Card>
  )
}
