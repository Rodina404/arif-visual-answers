import type { ProviderInfo, ProviderName } from '../api/client'
import { useI18n } from '../i18n/context'

const LABEL: Record<ProviderName, string> = { gemini: 'Gemini', groq: 'Groq' }

/** Gemini vs Groq for the next question. Unconfigured providers are shown but disabled. */
export function ProviderSwitch({
  providers,
  value,
  onChange,
}: {
  providers: ProviderInfo[]
  value: ProviderName
  onChange: (p: ProviderName) => void
}) {
  const { t } = useI18n()
  if (providers.length < 2) return null
  return (
    <div role="group" aria-label={t('provider.label')} data-testid="provider-switch" className="inline-flex rounded-full bg-raised p-0.5 text-sm">
      {providers.map((p) => (
        <button
          key={p.name}
          type="button"
          data-provider={p.name}
          aria-pressed={value === p.name}
          disabled={!p.available}
          title={p.available ? p.model : t('provider.unavailable', { name: LABEL[p.name] })}
          onClick={() => onChange(p.name)}
          className={`rounded-full px-3 py-1 font-semibold disabled:cursor-not-allowed disabled:opacity-40 ${
            value === p.name ? 'bg-accent text-on-accent' : 'text-muted hover:text-ink'
          }`}
        >
          {LABEL[p.name]}
        </button>
      ))}
    </div>
  )
}
