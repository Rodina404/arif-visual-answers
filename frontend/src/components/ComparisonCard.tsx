import type { ComparisonProps } from '../catalog/schemas'
import { stripUrls } from '../lib/text'
import type { Verification } from '../state/useAnswer'
import { Card } from './Card'
import { CitationChip } from './CitationChip'

export function ComparisonCard({ props, verification }: { props: ComparisonProps; verification?: Verification }) {
  const keys = props.items[0]?.attributes.map((a) => a.key) ?? []
  return (
    <Card lang={props.lang} type="comparison" title={props.title} verification={verification}>
      <div className="grid gap-3" style={{ gridTemplateColumns: `repeat(auto-fit, minmax(min(100%, 14rem), 1fr))` }}>
        {props.items.map((item, i) => (
          <article
            key={i}
            data-testid="comparison-item"
            className={`rounded-xl border p-3 ${i === props.items.length - 1 ? 'border-accent bg-accent-soft/60' : 'border-line bg-raised'}`}
          >
            <h4 dir="auto" className="m-0 text-sm font-semibold text-ink">
              <bdi>{stripUrls(item.name)}</bdi>
            </h4>
            <p dir="auto" className="mb-2 mt-1 text-xs leading-5 text-muted">
              {stripUrls(item.summary)}
            </p>
            <dl className="m-0 grid gap-2">
              {keys.map((k, j) => {
                const attr = item.attributes[j]
                return (
                  <div key={k} className="border-t border-line pt-2">
                    <dt dir="auto" className="text-xs font-semibold text-muted">
                      {stripUrls(k)}
                    </dt>
                    <dd dir="auto" className="m-0 text-sm text-ink">
                      <bdi>{stripUrls(attr?.value ?? '')}</bdi>
                      {attr?.citation ? <CitationChip citation={attr.citation} /> : null}
                    </dd>
                  </div>
                )
              })}
            </dl>
          </article>
        ))}
      </div>
    </Card>
  )
}
