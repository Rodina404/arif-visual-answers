import { useId, useState } from 'react'
import type { CitationT } from '../catalog/schemas'
import { useI18n } from '../i18n/context'
import { isMostlyLatin } from '../lib/text'
import { useApp } from '../state/context'

/** Small page chip. Hover/focus shows the verbatim quote; click opens the page in the source panel. */
export function CitationChip({ citation, page, label }: { citation?: CitationT; page?: number; label?: string }) {
  const { t } = useI18n()
  const { openSource } = useApp()
  const [show, setShow] = useState(false)
  const tipId = useId()
  const n = citation?.page ?? page
  if (!n) return null
  const quote = citation?.quote
  return (
    <span className="relative inline-flex align-baseline">
      <button
        type="button"
        data-testid="citation-chip"
        data-page={n}
        aria-label={quote ? `${t('cite.open', { n })}: ${quote}` : t('cite.open', { n })}
        aria-describedby={quote && show ? tipId : undefined}
        onClick={() => openSource({ page: n, quote })}
        onMouseEnter={() => setShow(true)}
        onMouseLeave={() => setShow(false)}
        onFocus={() => setShow(true)}
        onBlur={() => setShow(false)}
        className="mx-0.5 inline-flex items-center gap-1 rounded-full bg-accent-soft px-2 py-0 align-middle text-[11px] font-semibold leading-5 text-accent-strong hover:bg-accent hover:text-on-accent"
      >
        {label ? <bdi>{label}</bdi> : null}
        <span>{t('cite.page', { n })}</span>
      </button>
      {quote && show ? (
        <span
          id={tipId}
          role="tooltip"
          className="absolute top-full z-30 mt-1 w-72 max-w-[80vw] rounded-xl bg-surface p-3 text-xs font-normal text-ink shadow-float start-0"
        >
          <span className="mb-1 block text-muted">{t('cite.quote', { n })}</span>
          <q dir={isMostlyLatin(quote) ? 'ltr' : 'auto'} lang={isMostlyLatin(quote) ? 'en' : undefined} className="ltr-island">
            {quote}
          </q>
        </span>
      ) : null}
    </span>
  )
}
