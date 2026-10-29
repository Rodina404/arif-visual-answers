import { useEffect, useState } from 'react'
import { useI18n } from '../i18n/context'
import { stripUrls } from '../lib/text'

/** The short direct answer. Plain text (never markup); a live elapsed counter until the first token. */
export function AnswerText({
  text,
  lang,
  thinking,
  startedAt,
  long = false,
}: {
  text: string
  lang: 'ar' | 'en'
  thinking: boolean
  startedAt: number
  long?: boolean
}) {
  const { t, num } = useI18n()
  const [now, setNow] = useState(() => performance.now())
  useEffect(() => {
    if (!thinking) return
    const id = window.setInterval(() => setNow(performance.now()), 100)
    return () => window.clearInterval(id)
  }, [thinking])

  if (thinking && !text) {
    return (
      <p data-testid="thinking" role="status" className="m-0 flex items-center gap-2 text-sm text-muted">
        <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-accent" aria-hidden />
        {t('answer.thinking')}
        <span className="tabular-nums">{t('answer.elapsed', { s: num(Math.max(0, (now - startedAt) / 1000), { maximumFractionDigits: 1, minimumFractionDigits: 1 }) })}</span>
      </p>
    )
  }
  return (
    <p
      data-testid={long ? 'before-text' : 'answer-text'}
      dir={lang === 'ar' ? 'rtl' : 'ltr'}
      lang={lang}
      className={`m-0 whitespace-pre-line ${long ? 'text-[13px] leading-6 text-muted' : 'text-base leading-7 text-ink'}`}
    >
      {stripUrls(text)}
    </p>
  )
}
