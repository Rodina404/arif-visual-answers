import { useEffect, useRef, useState } from 'react'
import { getPage } from '../api/client'
import { useI18n } from '../i18n/context'
import { findQuote } from '../lib/text'
import type { SourceRequest } from '../state/context'

/** Side panel: the page's visible text with the cited quote highlighted. No PDF rendering needed. */
export function SourcePanel({ docId, req, onClose }: { docId: string; req: SourceRequest; onClose: () => void }) {
  const { t } = useI18n()
  const [text, setText] = useState<string | null>(null)
  const [error, setError] = useState(false)
  const closeRef = useRef<HTMLButtonElement>(null)
  const markRef = useRef<HTMLElement>(null)

  useEffect(() => {
    let live = true
    getPage(docId, req.page)
      .then((p) => live && setText(p.text))
      .catch(() => live && setError(true))
    return () => {
      live = false
    }
  }, [docId, req.page])

  useEffect(() => {
    closeRef.current?.focus()
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  useEffect(() => {
    markRef.current?.scrollIntoView?.({ block: 'center' })
  }, [text])

  const range = text && req.quote ? findQuote(text, req.quote) : null
  return (
    <aside
      role="dialog"
      aria-modal="false"
      aria-labelledby="source-title"
      data-testid="source-panel"
      className="fixed inset-y-0 end-0 z-40 flex w-full max-w-md flex-col bg-surface shadow-float"
    >
      <header className="flex items-center justify-between gap-2 px-4 py-3">
        <h2 id="source-title" className="m-0 text-base font-semibold">
          {t('source.title', { n: req.page })}
        </h2>
        <button
          ref={closeRef}
          type="button"
          onClick={onClose}
          className="rounded-full bg-raised px-4 py-1 text-sm font-semibold text-ink hover:bg-sunken"
        >
          {t('source.close')}
        </button>
      </header>
      <div className="flex-1 overflow-y-auto px-4 py-3">
        {text === null && !error ? <p className="text-sm text-muted">{t('source.loading')}</p> : null}
        {error || (text !== null && !text.trim()) ? <p className="text-sm text-muted">{t('source.notext')}</p> : null}
        {text ? (
          <pre dir="auto" data-testid="source-text" className="m-0 whitespace-pre-wrap break-words font-sans text-[13px] leading-6 text-ink">
            {range ? (
              <>
                {text.slice(0, range[0])}
                <mark ref={markRef} data-testid="source-highlight" className="rounded bg-mark px-0.5 text-ink">
                  {text.slice(range[0], range[1])}
                </mark>
                {text.slice(range[1])}
              </>
            ) : (
              text
            )}
          </pre>
        ) : null}
      </div>
    </aside>
  )
}
