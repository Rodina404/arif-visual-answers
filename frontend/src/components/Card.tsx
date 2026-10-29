import type { ReactNode } from 'react'
import { useI18n } from '../i18n/context'
import { useLeadTitle } from '../state/lead'
import type { Verification } from '../state/useAnswer'
import { TypeIcon } from './TypeIcon'

/** The one card level: a coloured band (type icon + label), the title, the body and verification notes. */
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
  const isLead = useLeadTitle() === title
  return (
    <section
      dir={lang === 'ar' ? 'rtl' : 'ltr'}
      lang={lang}
      data-component={type}
      data-verification={verification?.status}
      aria-label={title}
      className="fade-in overflow-hidden rounded-2xl bg-surface shadow-card"
    >
      <header
        className="flex items-center justify-between gap-2 px-4 py-1.5 text-white sm:px-5"
        style={{ background: `var(--color-band-${type}, var(--color-band-text))` }}
      >
        <span data-testid="type-band" className="flex items-center gap-2 text-xs font-semibold tracking-wide">
          <TypeIcon type={type} />
          <span className={lang === 'en' ? 'uppercase' : undefined}>{t(`type.${type}`)}</span>
        </span>
        {verification?.status === 'unverified' ? (
          <span data-testid="badge-unverified" className="rounded-full bg-white/20 px-2 py-0.5 text-[11px] font-semibold">
            {t('verify.unverified')}
          </span>
        ) : null}
      </header>
      <div className="grid gap-3 px-4 pb-4 pt-3 sm:px-5 sm:pb-5">
        <h3 dir="auto" className={isLead ? 'sr-only' : 'm-0 text-[17px] font-semibold leading-snug text-ink'}>
          {title}
        </h3>
        {children}
        {verification?.status === 'partial' || downgradedFrom ? (
          <p data-testid="partial-note" className="m-0 flex items-center gap-1.5 text-xs text-warn">
            <span aria-hidden>●</span>
            {downgradedFrom ? t('verify.downgraded') : t('verify.partial')}
          </p>
        ) : null}
      </div>
    </section>
  )
}
