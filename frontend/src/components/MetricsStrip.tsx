import { useI18n } from '../i18n/context'
import { fmtUsd } from '../lib/format'
import type { Metrics } from '../state/useAnswer'

export function MetricsStrip({ m }: { m: Metrics }) {
  const { t, num } = useI18n()
  const secs = m.latency_ms.total / 1000
  const shown = m.components.emitted
  const verified = m.components.verified
  return (
    <p data-testid="metrics-strip" className="m-0 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted tabular-nums">
      <bdi data-testid="metric-provider" className="rounded bg-raised px-1.5 font-semibold text-ink">
        {m.provider} · {m.model}
      </bdi>
      <span aria-hidden>·</span>
      <bdi data-testid="metric-time">⏱ {num(secs, { maximumFractionDigits: 1, minimumFractionDigits: 1 })}s</bdi>
      <span aria-hidden>·</span>
      <bdi>
        🧾 {num(m.tokens.total)} {t('metrics.tokens')}
      </bdi>
      <span aria-hidden>·</span>
      <bdi data-testid="metric-cost">{fmtUsd(m.cost_usd.total)}</bdi>
      {m.mode === 'visual' && shown > 0 ? (
        <>
          <span aria-hidden>·</span>
          <bdi data-testid="metric-verified">✓ {t('metrics.verified', { v: verified, n: shown })}</bdi>
        </>
      ) : null}
      {m.cache.app_cache_hit ? (
        <>
          <span aria-hidden>·</span>
          <span data-testid="metric-cached" className="rounded bg-ok-soft px-1.5 font-semibold text-ok">
            {t('metrics.cached')}
          </span>
        </>
      ) : null}
    </p>
  )
}
