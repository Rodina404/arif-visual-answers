import type { TableProps } from '../catalog/schemas'
import { useI18n } from '../i18n/context'
import { stripUrls } from '../lib/text'
import type { Verification } from '../state/useAnswer'
import { Card } from './Card'
import { CitationChip } from './CitationChip'

const NUMERIC = /^[\s\d.,%+\-–()BMK]+$/

export function DataTable({
  props,
  verification,
  downgradedFrom,
}: {
  props: TableProps
  verification?: Verification
  downgradedFrom?: string
}) {
  const { t } = useI18n()
  return (
    <Card lang={props.lang} type="table" title={props.title} verification={verification} downgradedFrom={downgradedFrom}>
      <div className="-mx-1 overflow-x-auto px-1">
        {/* A native table inside dir=rtl mirrors column order by itself. */}
        <table className="w-full border-separate border-spacing-0 text-sm">
          <thead>
            <tr>
              {props.columns.map((c, i) => (
                <th key={i} scope="col" dir="auto" className="px-3 pb-2 text-start text-xs font-semibold text-muted">
                  {stripUrls(c)}
                </th>
              ))}
              <th scope="col" className="w-14 px-2 pb-2">
                <span className="sr-only">{t('chart.sources')}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {props.rows.map((r, i) => (
              <tr key={i} data-testid="table-row" className="odd:bg-raised [&>td:first-child]:rounded-s-lg [&>td:last-child]:rounded-e-lg">
                {r.cells.map((cell, j) => {
                  const numeric = NUMERIC.test(cell)
                  return (
                    <td
                      key={j}
                      dir={numeric ? undefined : 'auto'}
                      className={`px-3 py-2.5 align-top text-ink ${j === 0 ? 'font-semibold' : ''} ${numeric ? 'text-end tabular-nums' : 'text-start'}`}
                    >
                      <bdi>{stripUrls(cell)}</bdi>
                    </td>
                  )
                })}
                <td className="px-2 py-2.5 text-end align-top">
                  <CitationChip citation={r.citation} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}
