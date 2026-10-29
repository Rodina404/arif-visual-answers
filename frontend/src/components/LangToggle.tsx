import { useI18n } from '../i18n/context'

export function LangToggle() {
  const { lang, setLang, t } = useI18n()
  return (
    <div role="group" aria-label={t('lang.toggle')} data-testid="lang-toggle" className="inline-flex rounded-full bg-raised p-0.5 text-sm">
      {(
        [
          ['ar', 'عربي'],
          ['en', 'English'],
        ] as const
      ).map(([l, label]) => (
        <button
          key={l}
          type="button"
          lang={l}
          aria-pressed={lang === l}
          onClick={() => setLang(l)}
          className={`rounded-full px-3 py-1 font-semibold ${lang === l ? 'bg-surface text-ink shadow-card' : 'text-muted hover:text-ink'}`}
        >
          {label}
        </button>
      ))}
    </div>
  )
}
