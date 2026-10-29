import type { ProviderName } from '../api/client'
import { useI18n } from '../i18n/context'
import { useAnswer } from '../state/useAnswer'
import { AnswerText } from './AnswerText'
import { errorMessage, fmtUsd } from '../lib/format'
import { AnswerView } from './AnswerView'
import { MetricsStrip } from './MetricsStrip'
import { QuestionBox } from './QuestionBox'

/** Same model, same question: a simulated text-only answer (left) vs the visual answer (right). */
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

  return (
    <div className="grid gap-4">
      <div className="rounded-2xl border border-line bg-surface p-4">
        <QuestionBox disabled={!docId} busy={busy} onAsk={(q) => run(q)} showTextOnly={false} submitLabel={t('compare.ask')} />
      </div>
      {b.phase === 'idle' && after.state.phase === 'idle' ? <p className="m-0 text-sm text-muted">{t('compare.pick')}</p> : null}
      {mb && ma ? (
        <p data-testid="compare-diff" className="m-0 rounded-xl bg-accent-soft px-3 py-2 text-sm text-accent">
          {t('compare.diff', {
            cost: `${fmtUsd(ma.cost_usd.total)} vs ${fmtUsd(mb.cost_usd.total)} (${pct(ma.cost_usd.total, mb.cost_usd.total)})`,
            time: `${num(ma.latency_ms.total / 1000, { maximumFractionDigits: 1 })}s vs ${num(mb.latency_ms.total / 1000, { maximumFractionDigits: 1 })}s`,
          })}
        </p>
      ) : null}
      {b.phase !== 'idle' || after.state.phase !== 'idle' ? (
        <div className="grid items-start gap-4 lg:grid-cols-2">
          <section data-testid="panel-before" aria-labelledby="before-title" className="grid gap-3 rounded-2xl border border-line bg-raised p-4">
            <h2 id="before-title" className="m-0 text-sm font-semibold text-muted">
              {t('compare.before')}
            </h2>
            <AnswerText text={b.text} lang={b.lang} thinking={b.phase === 'thinking'} startedAt={b.startedAt} long />
            {b.phase === 'error' ? (
              <p role="alert" className="m-0 text-sm text-bad">
                {errorMessage(t, b.error)}
              </p>
            ) : null}
            {mb ? <MetricsStrip m={mb} /> : null}
          </section>
          <section data-testid="panel-after" aria-labelledby="after-title" className="grid gap-3 rounded-2xl border border-accent/40 bg-bg p-4">
            <h2 id="after-title" className="m-0 text-sm font-semibold text-accent">
              {t('compare.after')}
            </h2>
            <AnswerView state={after.state} showDrawer={false} />
          </section>
        </div>
      ) : null}
    </div>
  )
}
