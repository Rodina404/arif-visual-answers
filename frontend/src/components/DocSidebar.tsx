import { useRef, useState } from 'react'
import type { UploadedDoc } from '../api/client'
import { useI18n } from '../i18n/context'

/** The user's documents: add several PDFs, switch between them, delete one (with a confirm step). */
export function DocSidebar({
  docs,
  activeId,
  busy,
  error,
  limits,
  onAdd,
  onSelect,
  onDelete,
}: {
  docs: UploadedDoc[]
  activeId: string | null
  busy: boolean
  error: string | null
  limits: { mb: number; pages: number }
  onAdd: (files: File[]) => void
  onSelect: (id: string) => void
  onDelete: (id: string) => void
}) {
  const { t, num } = useI18n()
  const input = useRef<HTMLInputElement>(null)
  const [confirm, setConfirm] = useState<string | null>(null)
  const [drag, setDrag] = useState(false)

  return (
    <aside
      aria-labelledby="docs-title"
      data-testid="doc-sidebar"
      onDragOver={(e) => {
        e.preventDefault()
        setDrag(true)
      }}
      onDragLeave={() => setDrag(false)}
      onDrop={(e) => {
        e.preventDefault()
        setDrag(false)
        onAdd(Array.from(e.dataTransfer.files))
      }}
      className={`grid content-start gap-3 rounded-2xl bg-surface p-3 shadow-card ${drag ? 'outline-2 outline-accent' : ''}`}
    >
      <div className="flex items-center justify-between gap-2 px-1">
        <h2 id="docs-title" className="m-0 text-sm font-bold text-ink">
          {t('docs.title')}
        </h2>
        <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-full bg-accent px-3 py-1.5 text-xs font-semibold text-on-accent hover:opacity-90">
          <input
            ref={input}
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
          <span aria-hidden>+</span>
          {busy ? t('upload.uploading') : t('docs.add')}
        </label>
      </div>
      {error ? (
        <p role="alert" data-testid="upload-error" className="m-0 rounded-xl bg-bad-soft px-3 py-2 text-xs text-bad">
          {t('upload.error')}: <bdi>{error}</bdi>
        </p>
      ) : null}
      {docs.length === 0 ? (
        <p className="m-0 px-1 pb-1 text-xs leading-5 text-muted">{t('upload.hint', { mb: limits.mb, pages: limits.pages })}</p>
      ) : (
        <ul className="m-0 grid list-none gap-1 p-0" data-testid="doc-list">
          {docs.map((d) => {
            const active = d.doc_id === activeId
            return (
              <li key={d.doc_id} data-testid="doc-item" data-active={active} data-doc-id={d.doc_id} className="group relative">
                <button
                  type="button"
                  onClick={() => onSelect(d.doc_id)}
                  aria-current={active ? 'true' : undefined}
                  className={`grid w-full gap-0.5 rounded-xl py-2 pe-9 ps-3 text-start ${active ? 'bg-accent-soft' : 'hover:bg-raised'}`}
                >
                  <bdi className={`truncate text-sm font-semibold ${active ? 'text-accent-strong' : 'text-ink'}`}>{d.filename}</bdi>
                  <span className="flex flex-wrap items-center gap-x-2 text-[11px] text-muted">
                    <span data-testid={active ? 'doc-pages' : undefined}>{t('upload.pages', { n: num(d.pages) })}</span>
                    {d.status === 'reading' ? (
                      <span data-testid="doc-reading" className="font-semibold text-warn">
                        {t('docs.reading')}
                      </span>
                    ) : d.ocr_pages.length ? (
                      <span>{t('docs.ocr')}</span>
                    ) : null}
                  </span>
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
                    className="absolute end-1 top-1.5 rounded-full bg-bad px-2.5 py-1 text-[11px] font-bold text-white"
                  >
                    {t('docs.confirmDelete')}
                  </button>
                ) : (
                  <button
                    type="button"
                    data-testid="doc-delete"
                    aria-label={t('docs.delete', { name: d.filename })}
                    onClick={() => setConfirm(d.doc_id)}
                    className="absolute end-1.5 top-2 flex h-7 w-7 items-center justify-center rounded-full text-muted hover:bg-bad-soft hover:text-bad"
                  >
                    <svg viewBox="0 0 16 16" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" aria-hidden>
                      <path d="M4 4l8 8M12 4l-8 8" />
                    </svg>
                  </button>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </aside>
  )
}
