import type { ComparisonProps } from '../catalog/schemas'
import { stripUrls } from '../lib/text'
import type { Verification } from '../state/useAnswer'
import { Card } from './Card'
import { CitationChip } from './CitationChip'

export function ComparisonCard({ props, verification }: { props: ComparisonProps; verification?: Verification }) {
  const keys = props.items[0]?.attributes.map((a) => a.key) ?? []
  const lastIndex = props.items.length - 1
  return (
    <Card lang={props.lang} type="comparison" title={props.title} verification={verification}>
      <div className="grid gap-3" style={{ gridTemplateColumns: `repeat(auto-fit, minmax(min(100%, 13rem), 1fr))` }}>
        {props.items.map((item, i) => {
          const lead = i === lastIndex
          return (
            <article key={i} data-testid="comparison-item" className={`rounded-xl px-3.5 py-3 ${lead ? 'bg-accent-soft' : 'bg-raised'}`}>
              <h4 dir="auto" className={`m-0 text-[15px] font-bold ${lead ? 'text-accent-strong' : 'text-ink'}`}>
                <bdi>{stripUrls(item.name)}</bdi>
              </h4>
              <p dir="auto" className="mb-3 mt-1 text-[13px] leading-5 text-muted">
                {stripUrls(item.summary)}
              </p>
              <dl className="m-0 grid gap-2.5">
                {keys.map((k, j) => {
                  const attr = item.attributes[j]
                  return (
                    <div key={k}>
                      <dt dir="auto" className="text-[11px] font-semibold text-muted">
                        {stripUrls(k)}
                      </dt>
                      <dd dir="auto" className="m-0 text-[15px] font-medium text-ink">
                        <bdi>{stripUrls(attr?.value ?? '')}</bdi>
                        {attr?.citation ? <CitationChip citation={attr.citation} /> : null}
                      </dd>
                    </div>
                  )
                })}
              </dl>
            </article>
          )
        })}
      </div>
    </Card>
  )
}
