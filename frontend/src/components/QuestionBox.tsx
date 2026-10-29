import { useState } from 'react'
import { useI18n } from '../i18n/context'

export interface Suggestion {
  id: string
  text: string
}

/** One-line question input with a send button; suggestions (demo or generated) as numbered rows. */
export function QuestionBox({
  disabled,
  busy,
  onAsk,
  onStop,
  showTextOnly = true,
  submitLabel,
  suggestions,
  suggestionsLoading = false,
}: {
  disabled: boolean
  busy: boolean
  onAsk: (question: string, textOnly: boolean) => void
  onStop?: () => void
  showTextOnly?: boolean
  submitLabel?: string
  suggestions: Suggestion[]
  suggestionsLoading?: boolean
}) {
  const { t, num } = useI18n()
  const [q, setQ] = useState('')
  const [textOnly, setTextOnly] = useState(false)
  const submit = (question: string) => {
    const trimmed = question.trim()
    if (!trimmed || disabled) return
    setQ(trimmed)
    onAsk(trimmed, textOnly)
  }
  return (
    <form
      className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-3"
      onSubmit={(e) => {
        e.preventDefault()
        submit(q)
      }}
    >
      <label htmlFor="question" className="sr-only">
        {t('ask.label')}
      </label>
      <div className="flex items-center gap-2 rounded-full bg-surface p-1.5 ps-5 shadow-card focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-accent">
        <input
          id="question"
          data-testid="question-input"
          dir="auto"
          type="text"
          maxLength={500}
          value={q}
          placeholder={disabled ? t('ask.needDoc') : t('ask.placeholder')}
          disabled={disabled}
          autoComplete="off"
          onChange={(e) => setQ(e.target.value)}
          className="min-w-0 flex-1 bg-transparent py-2 text-base text-ink outline-none placeholder:text-muted disabled:opacity-60"
        />
        {busy && onStop ? (
          <button type="button" onClick={onStop} className="h-11 shrink-0 rounded-full bg-raised px-5 text-sm font-semibold text-ink">
            {t('ask.stop')}
          </button>
        ) : (
          <button
            type="submit"
            data-testid="ask-button"
            disabled={disabled || !q.trim()}
            aria-label={submitLabel ?? t('ask.send')}
            className="flex h-11 shrink-0 items-center gap-2 rounded-full bg-accent px-5 text-sm font-semibold text-on-accent disabled:opacity-40"
          >
            <span>{submitLabel ?? t('ask.send')}</span>
            <svg viewBox="0 0 16 16" className="h-4 w-4 rtl:-scale-x-100" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <path d="M3 8h9M8.5 4l4 4-4 4" />
            </svg>
          </button>
        )}
      </div>
      <div className="grid gap-1.5">
        <div className="flex items-center justify-between gap-3 px-1">
          <span className="text-xs font-semibold text-muted">{t('ask.try')}</span>
          {showTextOnly ? (
            <label className="inline-flex cursor-pointer items-center gap-1.5 text-xs text-muted">
              <input type="checkbox" data-testid="text-only" checked={textOnly} onChange={(e) => setTextOnly(e.target.checked)} className="accent-[var(--color-accent)]" />
              {t('ask.textOnly')}
            </label>
          ) : null}
        </div>
        {suggestionsLoading ? (
          <p data-testid="suggestions-loading" className="m-0 px-1 text-xs text-muted">
            {t('ask.suggesting')}
          </p>
        ) : null}
        <ol className="m-0 grid list-none gap-1 p-0 sm:grid-cols-2">
          {suggestions.map(({ id, text }, i) => (
            <li key={id}>
              <button
                type="button"
                data-testid={`suggest-${id}`}
                disabled={disabled}
                onClick={() => submit(text)}
                className="flex w-full items-start gap-2.5 rounded-xl px-3 py-2 text-start text-sm text-ink hover:bg-surface hover:shadow-card disabled:opacity-50"
              >
                <span className="mt-px flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-accent-soft text-[11px] font-bold text-accent-strong tabular-nums">
                  {num(i + 1)}
                </span>
                <span dir="auto" className="min-w-0 leading-snug">
                  {text}
                </span>
              </button>
            </li>
          ))}
        </ol>
      </div>
    </form>
  )
}
