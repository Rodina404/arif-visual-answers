import type { ProviderName } from '../api/client'
import { useI18n } from '../i18n/context'
import { errorMessage, fmtUsd } from '../lib/format'
import { useAnswer } from '../state/useAnswer'
import { AnswerText } from './AnswerText'
import { AnswerView } from './AnswerView'
import { MetricsStrip } from './MetricsStrip'
import { QuestionBox } from './QuestionBox'

/** Same model, same question: a simulated text-only answer vs the visual answer, split by a "vs" badge. */
export function BeforeAfter({ docId, provider }: { docId: string | null; provider?: ProviderName }) {
  const { t, lang, num } = useI18n()
  const before = useAnswer()
  const after = useAnswer()
  const busy = ['thinking', 'streaming'].includes(before.state.phase) || ['thinking', 'streaming'].includes(after.state.phase)

  const run = (question: string) => {
    if (!docId) return
    void before.ask({ docId, question, lang, endpoint: '/api/ask_text', provider })
    void after.ask({ docId, question, lang, provider })
  }

  const mb = before.state.metrics
  const ma = after.state.metrics
  const pct = (a: number, b: number) => (b > 0 ? `${a >= b ? '+' : '−'}${num(Math.abs(Math.round(((a - b) / b) * 100)))}%` : '—')
  const b = before.state
  const words = b.text.trim() ? b.text.trim().split(/\s+/).length : 0
  const started = b.phase !== 'idle' || after.state.phase !== 'idle'

  return (
    <div className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-6">
      <QuestionBox disabled={!docId} busy={busy} onAsk={(q) => run(q)} showTextOnly={false} submitLabel={t('compare.ask')} />
      {!started ? <p className="m-0 py-4 text-center text-sm text-muted">{t('compare.pick')}</p> : null}
      {mb && ma ? (
        <p
          data-testid="compare-diff"
          className="m-0 justify-self-center rounded-full bg-accent-soft px-4 py-1.5 text-center text-sm font-semibold text-accent-strong"
        >
          {t('compare.diff', {
            cost: `${fmtUsd(ma.cost_usd.total)} vs ${fmtUsd(mb.cost_usd.total)} (${pct(ma.cost_usd.total, mb.cost_usd.total)})`,
            time: `${num(ma.latency_ms.total / 1000, { maximumFractionDigits: 1 })}s vs ${num(mb.latency_ms.total / 1000, { maximumFractionDigits: 1 })}s`,
          })}
        </p>
      ) : null}
      {started ? (
        <div className="grid items-start gap-4 sm:grid-cols-[minmax(0,0.8fr)_auto_minmax(0,1.35fr)]">
          <section data-testid="panel-before" aria-labelledby="before-title" className="grid min-w-0 gap-3">
            <h2 id="before-title" className="m-0 flex flex-wrap items-baseline gap-x-2 text-sm font-bold text-muted">
              <span>{t('compare.beforeLabel')}</span>
              {words ? <span className="text-xs font-normal">{t('compare.words', { n: num(words) })}</span> : null}
            </h2>
            <div className="relative max-h-[34rem] overflow-hidden">
              <div className={b.phase === 'thinking' ? undefined : 'wall-fade'}>
                <AnswerText text={b.text} lang={b.lang} thinking={b.phase === 'thinking'} startedAt={b.startedAt} long />
              </div>
              {b.text ? (
                <span aria-hidden className="absolute bottom-0 start-0 rounded-full bg-bg px-2 text-lg font-bold leading-6 text-muted">
                  …
                </span>
              ) : null}
            </div>
            {b.phase === 'error' ? (
              <p role="alert" className="m-0 text-sm text-bad">
                {errorMessage(t, b.error)}
              </p>
            ) : null}
            {mb ? <MetricsStrip m={mb} /> : null}
          </section>
          <div aria-hidden className="flex items-center gap-3 sm:h-full sm:flex-col">
            <span className="h-px flex-1 bg-line sm:h-auto sm:w-px" />
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-ink text-xs font-bold text-bg">
              {t('compare.vs')}
            </span>
            <span className="h-px flex-1 bg-line sm:h-auto sm:w-px" />
          </div>
          <section data-testid="panel-after" aria-labelledby="after-title" className="grid min-w-0 gap-3">
            <h2 id="after-title" className="m-0 text-sm font-bold text-accent-strong">
              {t('compare.afterLabel')}
            </h2>
            <AnswerView state={after.state} showDrawer={false} />
          </section>
        </div>
      ) : null}
    </div>
  )
}
