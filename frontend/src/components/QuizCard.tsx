import { useId, useRef, useState } from 'react'
import type { QuizProps } from '../catalog/schemas'
import { useI18n } from '../i18n/context'
import { stripUrls } from '../lib/text'
import type { Verification } from '../state/useAnswer'
import ClickSpark, { type ClickSparkHandle } from './bits/ClickSpark'
import { Card } from './Card'
import { CitationChip } from './CitationChip'

const SPARK_COLORS = ['#e2583e', '#0f9488', '#f2b84b']

function Question({ q, index, total, lang }: { q: QuizProps['questions'][number]; index: number; total: number; lang: 'ar' | 'en' }) {
  const { t } = useI18n()
  const name = useId()
  const sparks = useRef<ClickSparkHandle>(null)
  const grid = useRef<HTMLDivElement>(null)
  const tiles = useRef<(HTMLLabelElement | null)[]>([])
  const [choice, setChoice] = useState<number | null>(null)
  const checked = choice !== null
  const correct = checked && choice === q.correct_index

  const pick = (i: number) => {
    setChoice(i)
    if (i !== q.correct_index) return
    // Burst from the centre of the correct tile; with reduced motion ClickSpark draws a brief static flash.
    const tile = tiles.current[i]
    if (tile && grid.current) {
      const a = tile.getBoundingClientRect()
      const b = grid.current.getBoundingClientRect()
      sparks.current?.spark(a.left - b.left + a.width / 2, a.top - b.top + a.height / 2)
    }
  }

  return (
    <fieldset data-testid="quiz-question" className="m-0 grid min-w-0 gap-2.5 border-0 p-0">
      <legend className="sr-only">{t('quiz.question', { n: index + 1, total })}</legend>
      <p dir="auto" className="m-0 text-[15px] font-semibold text-ink">
        <span className="me-2 text-xs font-bold text-muted tabular-nums">
          {index + 1}/{total}
        </span>
        {stripUrls(q.prompt)}
      </p>
      <ClickSpark ref={sparks} sparkOnClick={false} sparkColor={SPARK_COLORS} sparkCount={12} sparkRadius={46} sparkSize={12} shape="star" duration={650}>
        <div ref={grid} className="grid grid-cols-2 gap-2">
          {q.options.map((opt, i) => {
            const state = checked ? (i === q.correct_index ? 'right' : i === choice ? 'wrong' : 'idle') : 'idle'
            const tone =
              state === 'right'
                ? 'bg-ok-soft text-ok'
                : state === 'wrong'
                  ? 'bg-bad-soft text-bad'
                  : checked
                    ? 'bg-raised text-muted'
                    : 'bg-raised text-ink hover:bg-sunken'
            return (
              <label
                key={i}
                ref={(el) => {
                  tiles.current[i] = el
                }}
                data-state={state}
                className={`relative flex min-h-16 cursor-pointer items-center gap-2 rounded-xl px-3 py-3 text-[15px] font-semibold transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-accent ${tone}`}
              >
                {/* The real radio covers the whole tile, so keyboard, screen readers and tests use it. */}
                <input
                  type="radio"
                  name={name}
                  value={i}
                  checked={choice === i}
                  onChange={() => pick(i)}
                  className="absolute inset-0 m-0 h-full w-full cursor-pointer appearance-none rounded-xl opacity-0"
                />
                <span
                  aria-hidden
                  className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs ${
                    state === 'right' ? 'bg-ok text-white' : state === 'wrong' ? 'bg-bad text-white' : 'bg-surface text-muted'
                  }`}
                >
                  {state === 'right' ? '✓' : state === 'wrong' ? '✕' : (lang === 'ar' ? 'أبجد' : 'ABCD')[i]}
                </span>
                <bdi dir="auto">{stripUrls(opt)}</bdi>
              </label>
            )
          })}
        </div>
      </ClickSpark>
      {checked ? (
        <div role="status" data-testid="quiz-feedback" data-correct={correct} className="text-sm">
          <p className={`m-0 font-bold ${correct ? 'text-ok' : 'text-bad'}`}>
            {correct ? t('quiz.correct') : t('quiz.incorrect', { a: stripUrls(q.options[q.correct_index]) })}
          </p>
          <p dir="auto" className="m-0 mt-1 leading-6 text-muted">
            {stripUrls(q.explanation)}
            <CitationChip citation={q.citation} />
          </p>
        </div>
      ) : null}
    </fieldset>
  )
}

export function QuizCard({ props, verification }: { props: QuizProps; verification?: Verification }) {
  return (
    <Card lang={props.lang} type="quiz" title={props.title} verification={verification}>
      <div className="grid gap-6">
        {props.questions.map((q, i) => (
          <Question key={i} q={q} index={i} total={props.questions.length} lang={props.lang} />
        ))}
      </div>
    </Card>
  )
}
