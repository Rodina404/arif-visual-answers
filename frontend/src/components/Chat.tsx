import { useState, type ReactNode } from 'react'
import logo from '../assets/arif-logo.png'
import { useI18n } from '../i18n/context'
import { FILE_INPUT_ID } from './DocBar'
import { Icon, type IconName } from './Icons'
import type { Suggestion } from './QuestionBox'
import { TypeIcon } from './TypeIcon'

export function Logo({ className = 'h-7 w-7' }: { className?: string }) {
  return <img src={logo} alt="" className={`${className} shrink-0 select-none`} draggable={false} />
}

/** The visual each demo question is expected to produce, used as the card icon. */
const DEMO_ICON: Record<string, string> = { q1: 'comparison', q2: 'chart', q3: 'table', q4: 'text', q5: 'flashcards', q6: 'diagram' }
const GENERIC_ICON: IconName[] = ['file', 'lines', 'shield', 'spark']

function SuggestionIcon({ id, i }: { id: string; i: number }) {
  return (
    <span aria-hidden className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent-soft text-accent-strong">
      {DEMO_ICON[id] ? <TypeIcon type={DEMO_ICON[id]} className="h-[18px] w-[18px]" /> : <Icon name={GENERIC_ICON[i % 4]} className="h-[18px] w-[18px]" />}
    </span>
  )
}

/** Welcome state: suggested questions as cards (icon, short title, the full question). */
export function SuggestionGrid({
  suggestions,
  loading,
  disabled,
  onPick,
}: {
  suggestions: Suggestion[]
  loading: boolean
  disabled: boolean
  onPick: (text: string) => void
}) {
  const { t } = useI18n()
  return (
    <section aria-labelledby="suggest-title" className="grid gap-3">
      <h3 id="suggest-title" className="m-0 text-xs font-normal text-muted">
        {t('widget.suggested')}
      </h3>
      {loading ? (
        <p data-testid="suggestions-loading" className="m-0 text-xs text-muted">
          {t('ask.suggesting')}
        </p>
      ) : null}
      <ul className="m-0 grid list-none grid-cols-[minmax(0,1fr)] gap-3 p-0 sm:grid-cols-2">
        {suggestions.map(({ id, text, title }, i) => (
          <li key={id} className="min-w-0">
            <button
              type="button"
              data-testid={`suggest-${id}`}
              disabled={disabled}
              onClick={() => onPick(text)}
              className="grid h-full w-full content-start justify-items-start gap-2.5 rounded-2xl border border-line bg-surface p-4 text-start hover:border-accent-line hover:shadow-card disabled:opacity-50"
            >
              <SuggestionIcon id={id} i={i} />
              <span className="grid gap-0.5">
                <span dir="auto" className="text-sm font-semibold leading-snug text-ink">
                  {title ?? text}
                </span>
                {title ? (
                  <span dir="auto" className="text-xs leading-snug text-muted">
                    {text}
                  </span>
                ) : null}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}

/** After an answer: the same suggestions as a row of small chips above the input. */
export function SuggestionChips({ suggestions, disabled, onPick }: { suggestions: Suggestion[]; disabled: boolean; onPick: (text: string) => void }) {
  const { t } = useI18n()
  if (!suggestions.length) return null
  return (
    <div className="flex min-w-0 items-center gap-1.5 overflow-x-auto pb-2" aria-label={t('widget.more')} role="group">
      {suggestions.map(({ id, text, title }) => (
        <button
          key={id}
          type="button"
          data-testid={`suggest-${id}`}
          disabled={disabled}
          onClick={() => onPick(text)}
          title={text}
          className="max-w-[16rem] shrink-0 truncate rounded-full border border-line bg-surface px-3 py-1 text-xs text-ink hover:border-accent-line disabled:opacity-50"
        >
          <bdi>{title ?? text}</bdi>
        </button>
      ))}
    </div>
  )
}

/** The input box: textarea with a purple border; attach + send on one row, settings and text-only next to send. */
export function Composer({
  disabled,
  busy,
  textOnly,
  onTextOnly,
  onAsk,
  onStop,
  onSettings,
  above,
}: {
  disabled: boolean
  busy: boolean
  textOnly: boolean
  onTextOnly: (v: boolean) => void
  onAsk: (question: string) => void
  onStop: () => void
  onSettings: () => void
  above?: ReactNode
}) {
  const { t } = useI18n()
  const [q, setQ] = useState('')
  const submit = () => {
    const trimmed = q.trim()
    if (!trimmed || disabled || busy) return
    setQ('')
    onAsk(trimmed)
  }
  return (
    <div className="grid gap-1 px-4 pb-3 pt-2 sm:px-5">
      {above}
      <form
        onSubmit={(e) => {
          e.preventDefault()
          submit()
        }}
        className="grid gap-2 rounded-[20px] border-[1.5px] border-accent-line bg-surface px-3 pb-2.5 pt-3 focus-within:border-accent"
      >
        <label htmlFor="question" className="sr-only">
          {t('ask.label')}
        </label>
        <textarea
          id="question"
          data-testid="question-input"
          dir="auto"
          rows={2}
          maxLength={500}
          value={q}
          placeholder={disabled ? t('ask.needDoc') : t('widget.placeholder')}
          disabled={disabled}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault()
              submit()
            }
          }}
          className="min-h-12 w-full resize-none bg-transparent px-1 text-[15px] leading-6 text-ink outline-none placeholder:text-faint disabled:opacity-60"
        />
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-1">
            <label
              htmlFor={FILE_INPUT_ID}
              title={t('widget.attach')}
              className="flex h-9 w-9 cursor-pointer items-center justify-center rounded-full text-muted hover:bg-raised hover:text-ink"
            >
              <Icon name="clip" />
              <span className="sr-only">{t('widget.attach')}</span>
            </label>
          </div>
          <div className="flex items-center gap-1.5">
            <label
              className={`inline-flex cursor-pointer items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ${textOnly ? 'bg-accent-soft text-accent-strong' : 'text-muted hover:bg-raised'}`}
            >
              <input
                type="checkbox"
                data-testid="text-only"
                checked={textOnly}
                onChange={(e) => onTextOnly(e.target.checked)}
                className="accent-[var(--color-accent)]"
              />
              {t('ask.textOnly')}
            </label>
            <button
              type="button"
              data-testid="settings-button"
              onClick={onSettings}
              aria-label={t('widget.settings')}
              className="flex h-9 w-9 items-center justify-center rounded-full text-muted hover:bg-raised hover:text-ink"
            >
              <Icon name="gear" />
            </button>
            {busy ? (
              <button
                type="button"
                onClick={onStop}
                aria-label={t('ask.stop')}
                className="flex h-10 w-10 items-center justify-center rounded-full bg-ink text-surface"
              >
                <Icon name="stop" className="h-4 w-4" />
              </button>
            ) : (
              <button
                type="submit"
                data-testid="ask-button"
                disabled={disabled || !q.trim()}
                aria-label={t('ask.send')}
                className="flex h-10 w-10 items-center justify-center rounded-full bg-accent text-on-accent disabled:bg-sunken disabled:text-muted"
              >
                <Icon name="send" className="h-[18px] w-[18px] rtl:-scale-x-100" />
              </button>
            )}
          </div>
        </div>
      </form>
      <p className="m-0 pt-1 text-center text-[11px] text-muted">{t('widget.disclaimer')}</p>
    </div>
  )
}

/** One chat turn: the question as a bubble on the end side, then Arif's reply under its name. */
export function Turn({ question, note, children }: { question: string; note?: string; children: ReactNode }) {
  const { t } = useI18n()
  return (
    <div className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-4">
      <p
        data-testid="user-bubble"
        dir="auto"
        className="m-0 max-w-[85%] justify-self-end rounded-2xl bg-raised px-4 py-2.5 text-sm leading-6 text-ink [overflow-wrap:anywhere]"
      >
        {question}
      </p>
      <div className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="flex items-center gap-1.5 text-sm font-bold text-ink">
            <Logo className="h-5 w-5" />
            {t('app.name')}
          </span>
        </div>
        {note ? (
          <p className="m-0 flex w-fit items-center gap-1.5 rounded-md border border-line bg-raised px-2 py-0.5 text-[11px] text-muted">
            <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-hot" />
            {note}
          </p>
        ) : null}
        {children}
      </div>
    </div>
  )
}
