import { useRef, useState } from 'react'
import { uploadDocument, type UploadedDoc } from '../api/client'
import { HttpError } from '../api/sse'
import { useI18n } from '../i18n/context'
import { Warnings } from './Warnings'

export function UploadPanel({
  doc,
  onUploaded,
  limits,
}: {
  doc: UploadedDoc | null
  onUploaded: (d: UploadedDoc) => void
  limits: { mb: number; pages: number }
}) {
  const { t, num } = useI18n()
  const input = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [drag, setDrag] = useState(false)

  async function send(file: File | undefined) {
    if (!file) return
    setBusy(true)
    setError(null)
    try {
      onUploaded(await uploadDocument(file))
    } catch (e) {
      setError(e instanceof HttpError ? (e.status === 429 ? t('error.rate') : e.message) : t('error.network'))
    } finally {
      setBusy(false)
      if (input.current) input.current.value = ''
    }
  }

  return (
    <section aria-labelledby="upload-title" className="grid gap-2">
      <div
        onDragOver={(e) => {
          e.preventDefault()
          setDrag(true)
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDrag(false)
          void send(e.dataTransfer.files[0])
        }}
        className={`flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-surface px-4 py-3 shadow-card ${drag ? 'outline-2 outline-accent' : ''}`}
      >
        <div className="min-w-0">
          <h2 id="upload-title" className="m-0 text-xs font-semibold text-muted">
            {t('upload.title')}
          </h2>
          {doc ? (
            <p data-testid="doc-info" className="m-0 truncate text-sm text-ink">
              <bdi className="font-semibold">{doc.filename}</bdi> · <span data-testid="doc-pages">{t('upload.pages', { n: num(doc.pages) })}</span>
            </p>
          ) : (
            <p className="m-0 text-sm text-muted">{t('upload.hint', { mb: limits.mb, pages: limits.pages })}</p>
          )}
        </div>
        <label className="inline-flex cursor-pointer items-center gap-2 rounded-full bg-accent-soft px-4 py-2 text-sm font-semibold text-accent-strong hover:bg-accent hover:text-on-accent">
          <input
            ref={input}
            data-testid="file-input"
            type="file"
            accept="application/pdf,.pdf"
            className="sr-only"
            disabled={busy}
            onChange={(e) => void send(e.target.files?.[0])}
          />
          {busy ? t('upload.uploading') : doc ? t('upload.replace') : t('upload.choose')}
        </label>
      </div>
      {error ? (
        <p role="alert" data-testid="upload-error" className="m-0 rounded-2xl bg-bad-soft px-4 py-2.5 text-sm text-bad">
          {t('upload.error')}: <bdi>{error}</bdi>
        </p>
      ) : null}
      {doc ? <Warnings items={doc.warnings} /> : null}
    </section>
  )
}
