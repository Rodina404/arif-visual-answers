import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { ChartProps } from '../catalog/schemas'
import { useI18n } from '../i18n/context'
import { stripUrls } from '../lib/text'
import type { Verification } from '../state/useAnswer'
import { Card } from './Card'
import { CitationChip } from './CitationChip'

const COLORS = ['var(--color-series-1)', 'var(--color-series-2)']
const FONT = '"IBM Plex Sans Arabic", "Noto Sans Arabic", system-ui, sans-serif'

export function ChartCard({ props, verification }: { props: ChartProps; verification?: Verification }) {
  const { num } = useI18n()
  const rtl = props.lang === 'ar'
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
  const tick = { fontFamily: FONT, fontSize: 12, fill: 'var(--color-muted)' }
  const common = { data, margin: { top: 8, right: 12, bottom: 24, left: 12 } }
  const axes = (
    <>
      <CartesianGrid stroke="var(--color-line)" strokeDasharray="3 3" vertical={false} />
      <XAxis
        dataKey="label"
        reversed={rtl}
        tick={tick}
        stroke="var(--color-line)"
        label={{ value: stripUrls(props.x_label), position: 'insideBottom', offset: -16, style: { ...tick, fill: 'var(--color-ink)' } }}
      />
      <YAxis
        orientation={rtl ? 'right' : 'left'}
        tick={tick}
        stroke="var(--color-line)"
        tickFormatter={(v: number) => fmt(v)}
        width={56}
        label={{ value: stripUrls(props.y_label), angle: rtl ? 90 : -90, position: rtl ? 'insideRight' : 'insideLeft', style: { ...tick, fill: 'var(--color-ink)', textAnchor: 'middle' } }}
      />
      <Tooltip
        formatter={(v) => fmt(Number(v))}
        contentStyle={{ direction: rtl ? 'rtl' : 'ltr', fontFamily: FONT, background: 'var(--color-surface)', border: '1px solid var(--color-line)', borderRadius: 8, color: 'var(--color-ink)' }}
      />
      <Legend align={rtl ? 'right' : 'left'} verticalAlign="top" wrapperStyle={{ fontFamily: FONT, fontSize: 12, paddingBottom: 8 }} />
    </>
  )

  return (
    <Card lang={props.lang} type="chart" title={props.title} verification={verification}>
      <div role="img" aria-label={`${props.title}. ${summary}`} data-testid="chart" className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          {props.chart_type === 'bar' ? (
            <BarChart {...common}>
              {axes}
              {props.series.map((s, i) => (
                <Bar key={i} dataKey={`s${i}`} name={stripUrls(s.name)} fill={COLORS[props.series.length === 1 ? 1 : i]} radius={[4, 4, 0, 0]} isAnimationActive={false} />
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
                  stroke={COLORS[props.series.length === 1 ? 1 : i]}
                  strokeWidth={2.5}
                  dot={{ r: 4 }}
                  isAnimationActive={false}
                />
              ))}
            </LineChart>
          )}
        </ResponsiveContainer>
      </div>
      <table className="sr-only">
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
      <div className="mt-2 grid gap-1">
        {props.series.map((s, i) => (
          <p key={i} data-testid="chart-sources" className="m-0 flex flex-wrap items-center gap-1 text-xs text-muted">
            <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: COLORS[props.series.length === 1 ? 1 : i] }} aria-hidden />
            <bdi className="me-1">{stripUrls(s.name)}</bdi>
            {s.points.map((p, j) => (
              <span key={j} data-testid="chart-point">
                <CitationChip citation={p.citation} label={`${p.label}: ${fmt(p.value)}`} />
              </span>
            ))}
          </p>
        ))}
      </div>
    </Card>
  )
}
