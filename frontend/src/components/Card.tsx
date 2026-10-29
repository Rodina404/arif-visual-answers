import type { ReactNode } from 'react'
import { useI18n } from '../i18n/context'
import type { Verification } from '../state/useAnswer'

/** Shared frame for every catalog component: direction from props.lang, title, verification notes. */
export function Card({
  lang,
  type,
  title,
  verification,
  downgradedFrom,
  children,
}: {
  lang: 'ar' | 'en'
  type: string
  title: string
  verification?: Verification
  downgradedFrom?: string
  children: ReactNode
}) {
  const { t } = useI18n()
  return (
    <section
      dir={lang === 'ar' ? 'rtl' : 'ltr'}
      lang={lang}
      data-component={type}
      data-verification={verification?.status}
      aria-label={title}
      className="fade-in rounded-2xl border border-line bg-surface p-4 shadow-sm sm:p-5"
    >
      <header className="mb-3 flex flex-wrap items-start justify-between gap-2">
        <h3 dir="auto" className="m-0 text-base font-semibold leading-snug text-ink">
          {title}
        </h3>
        {verification?.status === 'unverified' ? (
          <span data-testid="badge-unverified" className="rounded-full bg-warn-soft px-2 py-0.5 text-xs font-semibold text-warn">
            {t('verify.unverified')}
          </span>
        ) : null}
      </header>
      {children}
      {verification?.status === 'partial' || downgradedFrom ? (
        <p data-testid="partial-note" className="mb-0 mt-3 text-xs text-warn">
          {downgradedFrom ? t('verify.downgraded') : t('verify.partial')}
        </p>
      ) : null}
    </section>
  )
}
