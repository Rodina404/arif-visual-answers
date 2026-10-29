import { useId, useState } from 'react'
import type { QuizProps } from '../catalog/schemas'
import { useI18n } from '../i18n/context'
import { stripUrls } from '../lib/text'
import type { Verification } from '../state/useAnswer'
import { Card } from './Card'
import { CitationChip } from './CitationChip'

function Question({ q, index, total }: { q: QuizProps['questions'][number]; index: number; total: number }) {
  const { t } = useI18n()
  const name = useId()
  const [choice, setChoice] = useState<number | null>(null)
  const [checked, setChecked] = useState(false)
  const correct = checked && choice === q.correct_index
  return (
    <fieldset data-testid="quiz-question" className="m-0 rounded-xl border border-line bg-raised p-3">
      <legend className="sr-only">{t('quiz.question', { n: index + 1, total })}</legend>
      <p dir="auto" className="m-0 mb-2 text-sm font-semibold text-ink">
        {stripUrls(q.prompt)}
      </p>
      <div className="grid gap-1.5">
        {q.options.map((opt, i) => {
          const state = checked ? (i === q.correct_index ? 'right' : i === choice ? 'wrong' : 'idle') : 'idle'
          return (
            <label
              key={i}
              className={`flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm ${
                state === 'right' ? 'border-ok bg-ok-soft' : state === 'wrong' ? 'border-bad bg-bad-soft' : 'border-line bg-surface'
              }`}
            >
              <input
                type="radio"
                name={name}
                value={i}
                checked={choice === i}
                onChange={() => {
                  setChoice(i)
                  setChecked(true)
                }}
                className="accent-[var(--color-accent)]"
              />
              <bdi dir="auto" className="text-ink">
                {stripUrls(opt)}
              </bdi>
            </label>
          )
        })}
      </div>
      {checked ? (
        <div role="status" data-testid="quiz-feedback" data-correct={correct} className="mt-2 text-sm">
          <p className={`m-0 font-semibold ${correct ? 'text-ok' : 'text-bad'}`}>
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
      <div className="grid gap-3">
        {props.questions.map((q, i) => (
          <Question key={i} q={q} index={i} total={props.questions.length} />
        ))}
      </div>
    </Card>
  )
}
