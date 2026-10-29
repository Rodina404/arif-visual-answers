import { useI18n } from '../i18n/context'
import type { Metrics, Slot } from '../state/useAnswer'

export function MetricsDrawer({ m, slots }: { m: Metrics; slots: Slot[] }) {
  const { t, num } = useI18n()
  const r = m.retrieval
  const reasons = slots.flatMap((s) =>
    s.state === 'ready' ? [{ id: s.id, type: s.type, reason: String((s.props as { reason?: string }).reason ?? '') }] : [],
  )
  return (
    <details data-testid="metrics-drawer" className="group rounded-xl border border-line bg-surface text-sm">
      <summary className="cursor-pointer select-none px-3 py-2 text-xs font-semibold text-muted">{t('metrics.title')}</summary>
      <div className="grid gap-3 border-t border-line px-3 py-3">
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
          <pre data-testid="metrics-json" dir="ltr" className="m-0 max-h-72 overflow-auto rounded-lg bg-raised p-2 text-[11px] leading-4 text-ink">
            {JSON.stringify(m, null, 2)}
          </pre>
        </div>
      </div>
    </details>
  )
}
