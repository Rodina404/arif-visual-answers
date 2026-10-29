import { useRef, useState } from 'react'
import type { UploadedDoc } from '../api/client'
import { useI18n } from '../i18n/context'
import { Icon } from './Icons'

export const FILE_INPUT_ID = 'pdf-input'

/** "Working in": the user's documents as chips (switch, delete with a confirm step) and an add button. */
export function DocBar({
  docs,
  activeId,
  busy,
  onAdd,
  onSelect,
  onDelete,
}: {
  docs: UploadedDoc[]
  activeId: string | null
  busy: boolean
  onAdd: (files: File[]) => void
  onSelect: (id: string) => void
  onDelete: (id: string) => void
}) {
  const { t, num } = useI18n()
  const input = useRef<HTMLInputElement>(null)
  const [confirm, setConfirm] = useState<string | null>(null)

  return (
    <section
      aria-labelledby="docs-title"
      data-testid="doc-bar"
      className="flex min-w-0 items-center gap-2 border-b border-line bg-raised px-4 py-2.5 sm:px-5"
    >
      <h2 id="docs-title" className="m-0 flex shrink-0 items-center gap-1.5 text-xs font-normal text-muted">
        <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-accent" />
        {t('widget.context')}
      </h2>
      <ul className="m-0 flex min-w-0 flex-1 list-none items-center gap-1.5 overflow-x-auto p-0 py-0.5" data-testid="doc-list">
        {docs.map((d) => {
          const active = d.doc_id === activeId
          return (
            <li
              key={d.doc_id}
              data-testid="doc-item"
              data-active={active}
              data-doc-id={d.doc_id}
              className={`flex shrink-0 items-center rounded-full border text-xs ${active ? 'border-line bg-surface text-ink shadow-card' : 'border-transparent text-muted hover:bg-sunken'}`}
            >
              <button
                type="button"
                onClick={() => onSelect(d.doc_id)}
                aria-current={active ? 'true' : undefined}
                data-testid={active ? 'doc-info' : undefined}
                className="flex items-center gap-1.5 py-1 ps-2.5 pe-1"
              >
                <Icon name="file" className="h-3.5 w-3.5 shrink-0" />
                <bdi className="max-w-[11rem] truncate font-semibold">{d.filename}</bdi>
                <span aria-hidden className="h-3 w-px bg-line" />
                <span data-testid={active ? 'doc-pages' : undefined} className="text-muted">
                  {t('upload.pages', { n: num(d.pages) })}
                </span>
                {d.status === 'reading' ? (
                  <span data-testid="doc-reading" className="font-semibold text-warn">
                    {t('docs.reading')}
                  </span>
                ) : d.ocr_pages.length ? (
                  <span className="text-muted">{t('docs.ocr')}</span>
                ) : null}
              </button>
              {confirm === d.doc_id ? (
                <button
                  type="button"
                  data-testid="doc-delete-confirm"
                  onClick={() => {
                    setConfirm(null)
                    onDelete(d.doc_id)
                  }}
                  onBlur={() => setConfirm(null)}
                  className="me-1 rounded-full bg-bad px-2 py-0.5 text-[11px] font-bold text-white"
                >
                  {t('docs.confirmDelete')}
                </button>
              ) : (
                <button
                  type="button"
                  data-testid="doc-delete"
                  aria-label={t('docs.delete', { name: d.filename })}
                  onClick={() => setConfirm(d.doc_id)}
                  className="me-1 flex h-5 w-5 items-center justify-center rounded-full text-faint hover:bg-bad-soft hover:text-bad"
                >
                  <Icon name="close" className="h-3 w-3" />
                </button>
              )}
            </li>
          )
        })}
      </ul>
      <label
        title={t('docs.add')}
        className="inline-flex shrink-0 cursor-pointer items-center gap-1 rounded-full bg-accent-soft px-2.5 py-1 text-xs font-semibold text-accent-strong hover:bg-accent hover:text-on-accent"
      >
        <input
          ref={input}
          id={FILE_INPUT_ID}
          data-testid="file-input"
          type="file"
          multiple
          accept="application/pdf,.pdf"
          className="sr-only"
          disabled={busy}
          onChange={(e) => {
            onAdd(Array.from(e.target.files ?? []))
            if (input.current) input.current.value = ''
          }}
        />
        <Icon name="plus" className="h-3.5 w-3.5" />
        <span>{busy ? t('upload.uploading') : t('docs.add')}</span>
      </label>
    </section>
  )
}
