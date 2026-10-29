import { useState } from 'react'
import { useI18n } from '../i18n/context'
import { DEMO_QUESTIONS } from '../lib/format'

export function QuestionBox({
  disabled,
  busy,
  onAsk,
  onStop,
  showTextOnly = true,
  submitLabel,
}: {
  disabled: boolean
  busy: boolean
  onAsk: (question: string, textOnly: boolean) => void
  onStop?: () => void
  showTextOnly?: boolean
  submitLabel?: string
}) {
  const { t } = useI18n()
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
      className="grid gap-3"
      onSubmit={(e) => {
        e.preventDefault()
        submit(q)
      }}
    >
      <label htmlFor="question" className="text-xs font-semibold text-muted">
        {t('ask.label')}
      </label>
      <div className="flex flex-col gap-2 sm:flex-row">
        <textarea
          id="question"
          data-testid="question-input"
          dir="auto"
          rows={2}
          maxLength={500}
          value={q}
          placeholder={disabled ? t('ask.needDoc') : t('ask.placeholder')}
          disabled={disabled}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              submit(q)
            }
          }}
          className="min-h-12 flex-1 resize-y rounded-xl border border-line bg-surface px-3 py-2 text-base text-ink placeholder:text-muted disabled:opacity-60"
        />
        {busy && onStop ? (
          <button type="button" onClick={onStop} className="rounded-xl border border-line bg-surface px-5 py-2 font-semibold text-ink">
            {t('ask.stop')}
          </button>
        ) : (
          <button
            type="submit"
            data-testid="ask-button"
            disabled={disabled || !q.trim()}
            className="rounded-xl bg-accent px-5 py-2 font-semibold text-on-accent disabled:opacity-50"
          >
            {submitLabel ?? t('ask.submit')}
          </button>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-muted">{t('ask.suggestions')}:</span>
        {DEMO_QUESTIONS.map((id) => (
          <button
            key={id}
            type="button"
            data-testid={`suggest-${id}`}
            disabled={disabled}
            title={t(`q.${id}`)}
            onClick={() => submit(t(`q.${id}`))}
            className="rounded-full border border-line bg-surface px-3 py-1 text-xs text-ink hover:border-accent disabled:opacity-50"
          >
            {t(`q.short.${id}`)}
          </button>
        ))}
        {showTextOnly ? (
          <label className="ms-auto inline-flex cursor-pointer items-center gap-1.5 text-xs text-muted">
            <input type="checkbox" data-testid="text-only" checked={textOnly} onChange={(e) => setTextOnly(e.target.checked)} />
            {t('ask.textOnly')}
          </label>
        ) : null}
      </div>
    </form>
  )
}
