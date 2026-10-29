import katex from 'katex'
import { useEffect, useRef } from 'react'
import type { FormulaProps } from '../catalog/schemas'
import { stripUrls } from '../lib/text'
import type { Verification } from '../state/useAnswer'
import { Card } from './Card'
import { CitationChip } from './CitationChip'

export function FormulaCard({ props, verification }: { props: FormulaProps; verification?: Verification }) {
  const ref = useRef<HTMLSpanElement>(null)
  useEffect(() => {
    if (!ref.current) return
    // katex.render writes into the element itself (no raw-HTML React prop). trust:false blocks
    // \href, \url, \includegraphics and friends; maxSize/maxExpand bound the work.
    katex.render(props.latex, ref.current, {
      displayMode: true,
      throwOnError: false,
      trust: false,
      strict: 'warn',
      maxSize: 10,
      maxExpand: 100,
      output: 'htmlAndMathml',
    })
  }, [props.latex])
  return (
    <Card lang={props.lang} type="formula" title={props.title} verification={verification}>
      <span dir="ltr" className="ltr-island block overflow-x-auto py-2 text-ink">
        <span ref={ref} data-testid="formula" />
      </span>
      <p dir="auto" className="mb-0 mt-2 text-sm leading-6 text-muted">
        {stripUrls(props.explanation)}
        {props.citation ? <CitationChip citation={props.citation} /> : null}
      </p>
    </Card>
  )
}
