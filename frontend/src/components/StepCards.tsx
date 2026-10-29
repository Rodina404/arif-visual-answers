import type { StepsProps } from '../catalog/schemas'
import { useI18n } from '../i18n/context'
import { stripUrls } from '../lib/text'
import type { Verification } from '../state/useAnswer'
import { Card } from './Card'
import { CitationChip } from './CitationChip'

export function StepCards({ props, verification }: { props: StepsProps; verification?: Verification }) {
  const { t, num } = useI18n()
  return (
    <Card lang={props.lang} type="steps" title={props.title} verification={verification}>
      <ol className="m-0 grid list-none gap-4 p-0">
        {props.steps.map((s, i) => (
          <li key={i} data-testid="step" className="flex gap-3">
            <span
              aria-label={t('steps.step', { n: i + 1 })}
              className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-sm font-bold text-white"
              style={{ background: 'var(--color-band-steps)' }}
            >
              {num(i + 1)}
            </span>
            <div className="min-w-0 pt-0.5">
              <p dir="auto" className="m-0 text-[15px] font-semibold text-ink">
                {stripUrls(s.title)}
              </p>
              <p dir="auto" className="m-0 mt-0.5 text-sm leading-6 text-muted">
                {stripUrls(s.detail)}
                {s.page ? <CitationChip page={s.page} /> : null}
              </p>
            </div>
          </li>
        ))}
      </ol>
    </Card>
  )
}
