import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  deleteDocument,
  getConfig,
  getDocument,
  getSuggestions,
  listDocuments,
  uploadDocument,
  type ProviderName,
  type PublicConfig,
  type UploadedDoc,
} from './api/client'
import { HttpError } from './api/sse'
import { AnswerView } from './components/AnswerView'
import { BeforeAfter } from './components/BeforeAfter'
import { DocSidebar } from './components/DocSidebar'
import { LangToggle } from './components/LangToggle'
import { ProviderSwitch } from './components/ProviderSwitch'
import { QuestionBox, type Suggestion } from './components/QuestionBox'
import { SourcePanel } from './components/SourcePanel'
import { Warnings } from './components/Warnings'
import { useI18n } from './i18n/context'
import { DEMO_QUESTIONS } from './lib/format'
import { addToHistory, forgetHistory, loadHistory } from './lib/history'
import { AppContext, type SourceRequest } from './state/context'
import { useAnswer, type AnswerState } from './state/useAnswer'

type View = 'ask' | 'compare'
const PROVIDER_KEY = 'arif.provider'
const ACTIVE_KEY = 'arif.activeDoc'

function stored(key: string): string | null {
  try {
    return window.localStorage.getItem(key)
  } catch {
    return null
  }
}
function remember(key: string, value: string | null) {
  try {
    if (value === null) window.localStorage.removeItem(key)
    else window.localStorage.setItem(key, value)
  } catch {
    /* not remembered in private mode */
  }
}
function storedProvider(): ProviderName | null {
  const v = stored(PROVIDER_KEY)
  return v === 'gemini' || v === 'groq' ? v : null
}
const viewFromPath = (): View => (window.location.pathname.replace(/\/+$/, '') === '/compare' ? 'compare' : 'ask')

export default function App() {
  const { t, lang, setDigits } = useI18n()
  const [view, setView] = useState<View>(viewFromPath)
  const [docs, setDocs] = useState<UploadedDoc[]>([])
  const [activeId, setActiveId] = useState<string | null>(() => stored(ACTIVE_KEY))
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [config, setConfig] = useState<PublicConfig | null>(null)
  const [source, setSource] = useState<SourceRequest | null>(null)
  const [last, setLast] = useState<{ question: string; textOnly: boolean } | null>(null)
  const [provider, setProviderState] = useState<ProviderName | null>(storedProvider)
  const [historyVersion, setHistoryVersion] = useState(0)
  const [suggested, setSuggested] = useState<{ key: string; questions: string[] } | null>(null)
  const { state, ask, stop, restore } = useAnswer()
  // The answer on screen for each document, restored when switching back to it.
  const answers = useRef(new Map<string, AnswerState>())

  // The remembered document if it still exists (the server forgets documents after 48 h), else the newest.
  const currentId = docs.some((d) => d.doc_id === activeId) ? activeId : (docs[docs.length - 1]?.doc_id ?? null)
  const doc = docs.find((d) => d.doc_id === currentId) ?? null

  useEffect(() => {
    getConfig()
      .then((c) => {
        setConfig(c)
        setDigits(c.digits)
        // Keep a remembered choice only if that provider is usable on this server.
        setProviderState((p) => (p && c.providers.some((x) => x.name === p && x.available) ? p : c.provider))
      })
      .catch(() => setConfig(null))
    // Documents uploaded earlier (kept by the server for 48 h) come back after a reload.
    listDocuments()
      .then((list) => {
        // Merge: a document uploaded while this request was in flight must not disappear.
        setDocs((current) => [...list, ...current.filter((d) => !list.some((x) => x.doc_id === d.doc_id))])
      })
      .catch(() => setDocs([]))
  }, [setDigits])

  useEffect(() => {
    const onPop = () => setView(viewFromPath())
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])

  useEffect(() => {
    if (currentId) remember(ACTIVE_KEY, currentId)
  }, [currentId])
  // Re-read when the document changes or a question is added (historyVersion).
  const history = useMemo(() => (currentId && historyVersion >= 0 ? loadHistory(currentId) : []), [currentId, historyVersion])

  // While a scanned document is being read (OCR), poll until it is ready.
  const reading = docs.filter((d) => d.status === 'reading').map((d) => d.doc_id)
  const readingKey = reading.join(',')
  useEffect(() => {
    if (!readingKey) return
    const id = window.setInterval(async () => {
      const fresh = await Promise.all(readingKey.split(',').map((d) => getDocument(d).catch(() => null)))
      setDocs((list) => list.map((d) => fresh.find((f) => f?.doc_id === d.doc_id) ?? d))
    }, 1500)
    return () => window.clearInterval(id)
  }, [readingKey])

  // Suggestions: the prepared demo questions for the CoT paper, otherwise generated from the document.
  const suggestKey = doc && !doc.is_demo && doc.status === 'ready' ? `${doc.doc_id}:${lang}` : null
  useEffect(() => {
    if (!suggestKey) return
    const [docId, l] = suggestKey.split(':')
    let live = true
    getSuggestions(docId, l)
      .then((r) => live && setSuggested({ key: suggestKey, questions: r.questions }))
      .catch(() => live && setSuggested({ key: suggestKey, questions: [] }))
    return () => {
      live = false
    }
  }, [suggestKey])

  const suggestions: Suggestion[] = useMemo(() => {
    if (!doc) return []
    if (doc.is_demo) return DEMO_QUESTIONS.map((id) => ({ id, text: t(`q.${id}`) }))
    if (suggested?.key !== suggestKey) return []
    return suggested.questions.map((text, i) => ({ id: `g${i + 1}`, text }))
  }, [doc, suggested, suggestKey, t])
  const suggestionsLoading = Boolean(doc && !doc.is_demo && (doc.status === 'reading' || suggested?.key !== suggestKey))

  const go = (v: View) => {
    setView(v)
    window.history.pushState(null, '', v === 'compare' ? '/compare' : '/')
  }

  const setProvider = (p: ProviderName) => {
    setProviderState(p)
    remember(PROVIDER_KEY, p)
  }

  const select = useCallback(
    (id: string) => {
      if (id === currentId) return
      if (currentId) answers.current.set(currentId, state)
      restore(answers.current.get(id) ?? null)
      setLast(null)
      setActiveId(id)
    },
    [currentId, state, restore],
  )

  const addFiles = async (files: File[]) => {
    if (!files.length) return
    setUploading(true)
    setUploadError(null)
    let lastId: string | null = null
    for (const file of files) {
      try {
        const d = await uploadDocument(file)
        setDocs((list) => [...list.filter((x) => x.doc_id !== d.doc_id), d])
        lastId = d.doc_id
      } catch (e) {
        setUploadError(e instanceof HttpError ? (e.status === 429 ? t('error.rate') : e.message) : t('error.network'))
      }
    }
    setUploading(false)
    if (lastId) {
      if (currentId) answers.current.set(currentId, state)
      restore(null)
      setLast(null)
      setActiveId(lastId)
    }
  }

  const remove = async (id: string) => {
    try {
      await deleteDocument(id)
    } catch {
      /* already gone on the server: still remove it here */
    }
    forgetHistory(id)
    answers.current.delete(id)
    const rest = docs.filter((d) => d.doc_id !== id)
    setDocs(rest)
    if (id === currentId) {
      const next = rest[rest.length - 1]?.doc_id ?? null
      restore(next ? (answers.current.get(next) ?? null) : null)
      setActiveId(next)
    }
  }

  const run = useCallback(
    (question: string, textOnly: boolean) => {
      if (!doc) return
      setLast({ question, textOnly })
      addToHistory(doc.doc_id, question)
      setHistoryVersion((v) => v + 1)
      void ask({ docId: doc.doc_id, question, lang, textOnly, provider: provider ?? undefined })
    },
    [doc, ask, lang, provider],
  )

  const ctx = useMemo(() => ({ docId: doc?.doc_id ?? null, openSource: setSource }), [doc])
  const busy = state.phase === 'thinking' || state.phase === 'streaming'
  const canAsk = Boolean(doc && doc.status === 'ready')
  const earlier = history.filter((q) => q !== state.question)

  return (
    <AppContext.Provider value={ctx}>
      <div className="min-h-screen bg-bg text-ink">
        <header data-testid="app-header" className="sticky top-0 z-30 bg-bg/90 backdrop-blur">
          <div className="mx-auto flex max-w-[1060px] flex-wrap items-center justify-between gap-x-3 gap-y-2 px-4 py-3">
            <div data-testid="brand" className="flex min-w-0 items-center gap-2.5">
              <span aria-hidden className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-accent text-lg font-bold text-on-accent">
                ع
              </span>
              <div className="min-w-0">
                <h1 className="m-0 flex items-center gap-2 text-base font-bold leading-tight">
                  {t('app.title')}
                  {config?.mock ? (
                    <span data-testid="mock-badge" title={t('notice.mock')} className="rounded-full bg-hot px-2 py-0.5 text-[10px] font-bold text-white">
                      {t('badge.mock')}
                    </span>
                  ) : null}
                </h1>
                <p className="m-0 text-xs text-muted">{t('app.subtitle')}</p>
              </div>
            </div>
            <nav aria-label="views" className="flex flex-wrap items-center gap-1.5">
              <div className="flex rounded-full bg-raised p-0.5">
                {(['ask', 'compare'] as const).map((v) => (
                  <a
                    key={v}
                    href={v === 'compare' ? '/compare' : '/'}
                    data-testid={`tab-${v}`}
                    aria-current={view === v ? 'page' : undefined}
                    onClick={(e) => {
                      e.preventDefault()
                      go(v)
                    }}
                    className={`rounded-full px-3 py-1 text-sm font-semibold no-underline ${view === v ? 'bg-surface text-ink shadow-card' : 'text-muted hover:text-ink'}`}
                  >
                    {t(`tab.${v}`)}
                  </a>
                ))}
              </div>
              {config && provider ? <ProviderSwitch providers={config.providers} value={provider} onChange={setProvider} /> : null}
              <LangToggle />
            </nav>
          </div>
        </header>

        <div className="mx-auto grid max-w-[1060px] grid-cols-[minmax(0,1fr)] gap-6 px-4 pb-8 pt-2 lg:grid-cols-[260px_minmax(0,760px)]">
          <div className="lg:sticky lg:top-20 lg:self-start">
            <DocSidebar
              docs={docs}
              activeId={currentId}
              busy={uploading}
              error={uploadError}
              limits={{ mb: config?.max_upload_mb ?? 20, pages: config?.max_pages ?? 60 }}
              onAdd={(files) => void addFiles(files)}
              onSelect={select}
              onDelete={(id) => void remove(id)}
            />
          </div>

          <main className="grid min-w-0 grid-cols-[minmax(0,1fr)] content-start gap-6">
            {doc ? (
              <div data-testid="doc-info" className="flex flex-wrap items-baseline justify-between gap-2">
                <h2 className="m-0 min-w-0 truncate text-lg font-bold">
                  <bdi>{doc.filename}</bdi>
                </h2>
                {doc.status === 'reading' ? <span className="text-xs font-semibold text-warn">{t('docs.readingLong')}</span> : null}
              </div>
            ) : (
              <p className="m-0 rounded-2xl bg-surface px-4 py-6 text-center text-sm text-muted shadow-card">{t('docs.empty')}</p>
            )}
            {doc ? <Warnings items={doc.warnings} /> : null}
            {view === 'ask' ? (
              <>
                <QuestionBox
                  key={doc?.doc_id ?? 'none'}
                  disabled={!canAsk}
                  busy={busy}
                  onAsk={run}
                  onStop={stop}
                  suggestions={suggestions}
                  suggestionsLoading={suggestionsLoading}
                />
                {earlier.length ? (
                  <section aria-labelledby="history-title" data-testid="history" className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-1.5">
                    <h3 id="history-title" className="m-0 px-1 text-xs font-semibold text-muted">
                      {t('docs.history')}
                    </h3>
                    <div className="flex min-w-0 flex-wrap gap-1.5">
                      {earlier.slice(0, 6).map((q) => (
                        <button
                          key={q}
                          type="button"
                          data-testid="history-item"
                          disabled={!canAsk}
                          onClick={() => run(q, false)}
                          className="max-w-full truncate rounded-full bg-raised px-3 py-1 text-xs text-ink hover:bg-sunken"
                        >
                          <bdi>{q}</bdi>
                        </button>
                      ))}
                    </div>
                  </section>
                ) : null}
                {state.phase === 'idle' ? (
                  doc ? <p className="m-0 py-6 text-center text-sm text-muted">{t('answer.empty')}</p> : null
                ) : (
                  <AnswerView state={state} onRetry={last ? () => run(last.question, last.textOnly) : undefined} />
                )}
              </>
            ) : (
              <BeforeAfter
                key={doc?.doc_id ?? 'none'}
                docId={canAsk ? (doc?.doc_id ?? null) : null}
                provider={provider ?? undefined}
                suggestions={suggestions}
                suggestionsLoading={suggestionsLoading}
              />
            )}
          </main>
        </div>

        <footer className="mx-auto grid max-w-[1060px] gap-1 px-4 pb-10 pt-2 text-xs text-muted">
          <p data-testid="residency-badge" className="m-0">
            {t('footer.residency')}
          </p>
          <p data-testid="demo-notice" className="m-0">
            {t('notice.demo')}
          </p>
        </footer>

        {source && doc ? (
          <SourcePanel key={`${doc.doc_id}:${source.page}:${source.quote ?? ''}`} docId={doc.doc_id} req={source} onClose={() => setSource(null)} />
        ) : null}
      </div>
    </AppContext.Provider>
  )
}
