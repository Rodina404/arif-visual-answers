import { useI18n } from '../i18n/context'
import type { Metrics, Slot, ToolCall } from '../state/useAnswer'

interface AuditRow {
  id: string
  name: string
  input: string
  status: ToolCall['status']
  durationMs?: number
  summary?: string
}

/** A plain answer has no tool calls: its audit is the pipeline's own steps, taken from the metrics. */
function pipelineSteps(m: Metrics, t: (k: string, v?: Record<string, string | number>) => string): AuditRow[] {
  const r = m.retrieval
  const pages = r && r.retrieval === 'bm25' && r.pages ? r.pages.join(', ') : null
  const rows: AuditRow[] = [
    {
      id: 'retrieve',
      name: t('audit.retrieve'),
      input: pages ? `pages=${pages}` : t('metrics.retrievalOff'),
      status: 'ok',
    },
    {
      id: 'generate',
      name: t('audit.generate'),
      input: `${m.provider} · ${m.model}`,
      status: 'ok',
      durationMs: m.latency_ms.total,
      summary: `${m.tokens.total} tokens`,
    },
  ]
  if (m.mode === 'visual') {
    rows.push({
      id: 'verify',
      name: t('audit.verify'),
      input: `${m.components.emitted + m.components.dropped} components`,
      status: 'ok',
      summary: t('metrics.verified', { v: m.components.verified, n: m.components.emitted }),
    })
  }
  return rows
}

const DOT: Record<ToolCall['status'], string> = {
  running: 'bg-faint',
  ok: 'bg-ok',
  proposed: 'bg-accent',
  error: 'bg-bad',
}

export function MetricsDrawer({ m, slots, tools = [] }: { m: Metrics; slots: Slot[]; tools?: ToolCall[] }) {
  const { t, num } = useI18n()
  const r = m.retrieval
  const reasons = slots.flatMap((s) =>
    s.state === 'ready' ? [{ id: s.id, type: s.type, reason: String((s.props as { reason?: string }).reason ?? '') }] : [],
  )
  const rows: AuditRow[] = tools.length
    ? tools.map((c) => ({ ...c, name: t(`tool.${c.name}`) === `tool.${c.name}` ? c.name : t(`tool.${c.name}`) }))
    : pipelineSteps(m, t)
  const completed = rows.filter((x) => x.status === 'ok' || x.status === 'proposed').length
  return (
    <details data-testid="metrics-drawer" className="group rounded-2xl border border-line bg-surface text-sm">
      <summary className="flex cursor-pointer list-none items-center gap-3 px-4 py-2.5 select-none [&::-webkit-details-marker]:hidden">
        <span className="text-xs font-semibold text-ink">{t('metrics.title')}</span>
        <span data-testid="audit-count" className="text-xs font-semibold text-muted">
          {t('metrics.completed', { n: num(completed) })}
        </span>
        <svg viewBox="0 0 24 24" className="ms-auto h-4 w-4 text-muted transition-transform group-open:rotate-180" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
          <path d="m6 9 6 6 6-6" />
        </svg>
      </summary>
      <div className="grid gap-3 border-t border-line px-4 pb-3 pt-3">
        <ol data-testid="audit-list" className="m-0 grid list-none gap-1.5 p-0">
          {rows.map((row, i) => (
            <li key={row.id} data-testid="audit-row" data-status={row.status} className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-start gap-x-2.5 rounded-lg bg-raised px-2.5 py-2">
              <span aria-hidden className={`mt-1.5 h-2 w-2 rounded-full ${DOT[row.status]}`} />
              <span className="grid min-w-0 gap-0.5">
                <span className="text-xs font-semibold text-ink">
                  {num(i + 1)}. {row.name}
                  <span className="ms-2 font-normal text-muted">{t(`audit.status.${row.status}`)}</span>
                </span>
                {/* Inputs mix Arabic and English: a monospace font would break Arabic letter joining. */}
                <span dir="auto" className="truncate text-start text-[11px] text-muted">
                  {row.input}
                </span>
                {row.summary ? (
                  <span dir="auto" className="text-[11px] text-muted">
                    {row.summary}
                  </span>
                ) : null}
              </span>
              <bdi className="text-[11px] tabular-nums text-muted">{row.durationMs !== undefined ? `${num(row.durationMs)} ms` : ''}</bdi>
            </li>
          ))}
        </ol>
        <div data-testid="metrics-retrieval">
          <h4 className="m-0 mb-1 text-xs font-semibold text-muted">{t('metrics.retrieval')}</h4>
          <p className="m-0 text-xs text-ink">
            {r && r.retrieval === 'bm25' && r.pages
              ? t('metrics.retrievalPages', {
                  n: num(r.pages.length),
                  tokens: num(r.context_tokens_est ?? 0),
                  pages: r.pages.map((p) => num(p)).join(', '),
                })
              : t('metrics.retrievalOff')}
          </p>
        </div>
        {reasons.length ? (
          <div>
            <h4 className="m-0 mb-1 text-xs font-semibold text-muted">{t('metrics.reasons')}</h4>
            <ul className="m-0 grid list-none gap-1 p-0" dir="ltr">
              {reasons.map((r) => (
                <li key={r.id} className="text-xs text-ink">
                  <code className="rounded bg-raised px-1">{r.type}</code> {r.reason}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        <div>
          <h4 className="m-0 mb-1 text-xs font-semibold text-muted">{t('metrics.raw')}</h4>
          <pre
            data-testid="metrics-json"
            dir="ltr"
            tabIndex={0}
            role="region"
            aria-label={t('metrics.raw')}
            className="m-0 max-h-72 overflow-auto rounded-xl bg-raised p-2 text-[11px] leading-4 text-ink">
            {JSON.stringify(m, null, 2)}
          </pre>
        </div>
      </div>
    </details>
  )
}
