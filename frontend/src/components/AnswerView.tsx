import { Suspense } from 'react'
import { REGISTRY } from '../catalog/registry'
import { isComponentType } from '../catalog/schemas'
import { useI18n } from '../i18n/context'
import { errorMessage } from '../lib/format'
import type { AnswerState } from '../state/useAnswer'
import { AnswerText } from './AnswerText'
import { ErrorBoundary } from './ErrorBoundary'
import { MetricsDrawer } from './MetricsDrawer'
import { MetricsStrip } from './MetricsStrip'
import { Skeleton } from './Skeletons'
import { Warnings } from './Warnings'

function DroppedNote({ fallback }: { fallback?: string }) {
  const { t } = useI18n()
  return (
    <div data-testid="dropped-note" className="rounded-xl border border-dashed border-line px-3 py-2 text-sm text-muted">
      <p className="m-0">{t('dropped.note')}</p>
      {fallback ? (
        <p dir="auto" className="m-0 mt-1 text-ink">
          <bdi>{fallback}</bdi>
        </p>
      ) : null}
    </div>
  )
}

export function AnswerView({ state, onRetry, showDrawer = true }: { state: AnswerState; onRetry?: () => void; showDrawer?: boolean }) {
  const { t } = useI18n()
  if (state.phase === 'idle') return null
  const thinking = state.phase === 'thinking' || (state.phase === 'streaming' && !state.text)
  return (
    <div data-testid="answer" data-phase={state.phase} className="grid gap-4">
      <Warnings items={state.warnings} />
      {state.text || thinking ? (
        <AnswerText text={state.text} lang={state.lang} thinking={thinking} startedAt={state.startedAt} />
      ) : null}
      {state.slots.length ? (
        <div data-testid="components" className="grid gap-4">
          {state.slots.map((slot) => {
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
          })}
        </div>
      ) : null}
      {state.phase === 'error' && state.error ? (
        <div role="alert" data-testid="run-error" data-code={state.error.code} className="flex flex-wrap items-center gap-3 rounded-xl border border-bad/40 bg-bad-soft px-3 py-2 text-sm text-bad">
          <span>{errorMessage(t, state.error)}</span>
          {onRetry ? (
            <button type="button" onClick={onRetry} className="rounded-lg border border-bad/50 bg-surface px-3 py-1 font-semibold text-bad">
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
