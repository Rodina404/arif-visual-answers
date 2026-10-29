import { Suspense, type ReactNode } from 'react'
import { REGISTRY } from '../catalog/registry'
import { isComponentType, type ChartProps } from '../catalog/schemas'
import { useI18n } from '../i18n/context'
import { errorMessage } from '../lib/format'
import { keyStat, type Stat } from '../lib/keyNumbers'
import { LeadContext } from '../state/lead'
import type { AnswerState, Slot } from '../state/useAnswer'
import { AnswerText } from './AnswerText'
import { ErrorBoundary } from './ErrorBoundary'
import { MetricsDrawer } from './MetricsDrawer'
import { MetricsStrip } from './MetricsStrip'
import { Skeleton } from './Skeletons'
import { StatNumber } from './StatNumber'
import { Warnings } from './Warnings'

function DroppedNote({ fallback }: { fallback?: string }) {
  const { t } = useI18n()
  return (
    <div data-testid="dropped-note" className="rounded-2xl bg-raised px-4 py-3 text-sm text-muted">
      <p className="m-0">{t('dropped.note')}</p>
      {fallback ? (
        <p dir="auto" className="m-0 mt-1 text-ink">
          <bdi>{fallback}</bdi>
        </p>
      ) : null}
    </div>
  )
}

/** The headline number next to the takeaway: the chart's largest verified gap (or peak). */
function KeyNumber({ stat, unit }: { stat: Stat; unit: string }) {
  const { t, num } = useI18n()
  const label =
    stat.kind === 'value'
      ? t('key.peak', { label: stat.label })
      : unit === '%'
        ? t('key.pointsAt', { label: stat.label })
        : t('key.unitAt', { unit, label: stat.label })
  return (
    <div data-testid="key-number" className="shrink-0 text-end">
      <div className="text-4xl font-bold leading-none text-hot tabular-nums">
        <StatNumber stat={stat} />
      </div>
      <div className="mt-1 text-xs font-semibold text-ink">
        <bdi>{label}</bdi>
      </div>
      {stat.kind === 'gap' && stat.from !== undefined && stat.to !== undefined ? (
        <div className="text-[11px] text-muted tabular-nums">
          <bdi>
            {t('key.from', { a: `${num(stat.from)}${unit}`, b: `${num(stat.to)}${unit}` })} · p.{stat.citation.page}
          </bdi>
        </div>
      ) : null}
    </div>
  )
}

function renderSlot(slot: Slot): ReactNode {
  if (slot.state === 'planned') return <Skeleton key={slot.id} type={slot.type} />
  if (slot.state === 'dropped') return <DroppedNote key={slot.id} fallback={slot.fallbackText} />
  if (!isComponentType(slot.type)) return null
  const Renderer = REGISTRY[slot.type]
  return (
    <div key={slot.id} data-testid="component" data-type={slot.type} data-id={slot.id}>
      <ErrorBoundary fallback={<DroppedNote />}>
        <Suspense fallback={<Skeleton type={slot.type} />}>
          <Renderer props={slot.props as never} verification={slot.verification} downgradedFrom={slot.downgradedFrom} />
        </Suspense>
      </ErrorBoundary>
    </div>
  )
}

export function AnswerView({ state, onRetry, showDrawer = true }: { state: AnswerState; onRetry?: () => void; showDrawer?: boolean }) {
  const { t } = useI18n()
  if (state.phase === 'idle') return null
  const thinking = state.phase === 'thinking' || (state.phase === 'streaming' && !state.text)
  // Lead with the visual: the first component's title becomes the takeaway headline.
  const first = state.slots[0]
  const lead = first?.state === 'ready' ? (first.props as { title: string; lang: 'ar' | 'en' }) : null
  const chart = state.slots.find((s) => s.state === 'ready' && s.type === 'chart')
  const chartProps = chart && chart.state === 'ready' ? (chart.props as ChartProps) : null
  const key = chartProps ? keyStat(chartProps) : null
  const text =
    state.text || thinking ? <AnswerText text={state.text} lang={state.lang} thinking={thinking} startedAt={state.startedAt} /> : null

  return (
    <div data-testid="answer" data-phase={state.phase} className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-5">
      <Warnings items={state.warnings} />
      {lead ? (
        <div data-testid="takeaway" dir={lead.lang === 'ar' ? 'rtl' : 'ltr'} lang={lead.lang} className="flex items-start justify-between gap-4">
          <h2 dir="auto" className="m-0 text-2xl font-bold leading-tight text-ink [text-wrap:balance] sm:text-[28px]">
            {lead.title}
          </h2>
          {key && chartProps ? <KeyNumber stat={key} unit={chartProps.unit} /> : null}
        </div>
      ) : null}
      {/* Until the first visual is ready, the answer text keeps its place at the top. */}
      {!lead ? text : null}
      {state.slots.length ? (
        <LeadContext.Provider value={lead?.title ?? null}>
          <div data-testid="components" className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-5">
            {renderSlot(state.slots[0])}
            {lead ? text : null}
            {state.slots.slice(1).map(renderSlot)}
          </div>
        </LeadContext.Provider>
      ) : null}
      {state.phase === 'error' && state.error ? (
        <div
          role="alert"
          data-testid="run-error"
          data-code={state.error.code}
          className="flex flex-wrap items-center gap-3 rounded-2xl bg-bad-soft px-4 py-3 text-sm text-bad"
        >
          <span>{errorMessage(t, state.error)}</span>
          {onRetry ? (
            <button type="button" onClick={onRetry} className="rounded-full bg-surface px-4 py-1.5 font-semibold text-bad shadow-card">
              {t('answer.retry')}
            </button>
          ) : null}
        </div>
      ) : null}
      {state.metrics ? (
        <div className="grid gap-2">
          <MetricsStrip m={state.metrics} />
          {showDrawer ? <MetricsDrawer m={state.metrics} slots={state.slots} /> : null}
        </div>
      ) : null}
    </div>
  )
}
