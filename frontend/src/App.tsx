import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
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
import { Composer, Logo, SuggestionChips, SuggestionGrid, Turn } from './components/Chat'
import { DocBar, FILE_INPUT_ID } from './components/DocBar'
import { Icon } from './components/Icons'
import { Menu, MenuRow } from './components/Menu'
import { LangToggle } from './components/LangToggle'
import { ProviderSwitch } from './components/ProviderSwitch'
import type { Suggestion } from './components/QuestionBox'
import { SourcePanel } from './components/SourcePanel'
import { TasksView } from './components/TasksView'
import { TypeIcon } from './components/TypeIcon'
import { Warnings } from './components/Warnings'
import { useI18n } from './i18n/context'
import { DEMO_QUESTIONS } from './lib/format'
import { addToHistory, forgetHistory, loadHistory } from './lib/history'
import { AppContext, type SourceRequest } from './state/context'
import { useAnswer, type AnswerState } from './state/useAnswer'

type View = 'ask' | 'compare' | 'tasks'
const PATHS: Record<View, string> = { ask: '/', compare: '/compare', tasks: '/tasks' }
// The SAMPLE meeting transcript's prepared questions (agent mode).
const MEETING_QUESTIONS = ['decisions', 'owners', 'tasks', 'email']
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
// The model choice lasts for this tab only (survives reloads); a new visit starts on the server's PROVIDER.
function storedProvider(): ProviderName | null {
  let v: string | null = null
  try {
    v = window.sessionStorage.getItem(PROVIDER_KEY)
  } catch {
    /* private mode */
  }
  return v === 'gemini' || v === 'groq' ? v : null
}
const viewFromPath = (): View => {
  const path = window.location.pathname.replace(/\/+$/, '')
  return path === '/compare' ? 'compare' : path === '/tasks' ? 'tasks' : 'ask'
}

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
  const [menuOpen, setMenuOpen] = useState(false)
  const [windowOpen, setWindowOpen] = useState(true)
  const [textOnly, setTextOnly] = useState(false)
  const turnRef = useRef<HTMLDivElement>(null)
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
  const suggestKey = doc && !doc.is_demo && !doc.demo && doc.status === 'ready' ? `${doc.doc_id}:${lang}` : null
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
    if (doc.is_demo) return DEMO_QUESTIONS.map((id) => ({ id, text: t(`q.${id}`), title: t(`q.short.${id}`) }))
    if (doc.demo === 'meeting')
      return MEETING_QUESTIONS.map((id) => ({ id, text: t(`q.meeting.${id}`), title: t(`q.meeting.short.${id}`) }))
    if (suggested?.key !== suggestKey) return []
    return suggested.questions.map((text, i) => ({ id: `g${i + 1}`, text }))
  }, [doc, suggested, suggestKey, t])
  const suggestionsLoading = Boolean(doc && !doc.is_demo && !doc.demo && (doc.status === 'reading' || suggested?.key !== suggestKey))

  const go = (v: View) => {
    setView(v)
    setMenuOpen(false)
    window.history.pushState(null, '', PATHS[v])
  }

  const setProvider = (p: ProviderName) => {
    setProviderState(p)
    try {
      window.sessionStorage.setItem(PROVIDER_KEY, p)
    } catch {
      /* not remembered in private mode */
    }
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

  const busy = state.phase === 'thinking' || state.phase === 'streaming'
  // Bring each new question to the top of the conversation.
  useEffect(() => {
    if (state.phase === 'thinking') turnRef.current?.scrollIntoView({ block: 'start' })
  }, [state.phase, state.question])

  const newChat = () => {
    if (busy) stop()
    restore(null)
    setLast(null)
  }
  const closeMenu = useCallback(() => setMenuOpen(false), [])

  const ctx = useMemo(() => ({ docId: doc?.doc_id ?? null, openSource: setSource }), [doc])
  const canAsk = Boolean(doc && doc.status === 'ready')
  const earlier = history.filter((q) => q !== state.question)

  const header: ReactNode = (
    <header data-testid="app-header" className="relative flex items-center justify-between gap-3 border-b border-line px-4 py-3 sm:px-5">
      <div data-testid="brand" className="flex min-w-0 items-center gap-3">
        <span className="flex shrink-0 items-center gap-2">
          <Logo className="h-8 w-8" />
          <h1 className="m-0 text-lg font-bold leading-none text-ink">{t('app.name')}</h1>
        </span>
        <span aria-hidden className="h-6 w-px shrink-0 bg-line" />
        <span className="flex min-w-0 items-center gap-1.5 rounded-full bg-accent-soft px-3 py-1 text-xs font-semibold text-accent-strong max-sm:hidden">
          <span aria-hidden className="h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
          <span className="truncate">{t(view === 'ask' ? 'widget.mode' : `tab.${view}`)}</span>
        </span>
        {config?.mock ? (
          <span data-testid="mock-badge" title={t('notice.mock')} className="shrink-0 rounded-full bg-hot px-2 py-0.5 text-[10px] font-bold text-white">
            {t('badge.mock')}
          </span>
        ) : null}
      </div>
      <div className="flex shrink-0 items-center gap-0.5 text-muted">
        <button
          type="button"
          data-testid="tasks-button"
          onClick={() => go(view === 'tasks' ? 'ask' : 'tasks')}
          aria-label={t('tab.tasks')}
          aria-pressed={view === 'tasks'}
          title={t('tab.tasks')}
          className={`flex h-9 w-9 items-center justify-center rounded-full hover:bg-raised hover:text-ink ${view === 'tasks' ? 'bg-accent-soft text-accent-strong' : ''}`}
        >
          <TypeIcon type="task_cards" className="h-[18px] w-[18px]" />
        </button>
        <button
          type="button"
          data-testid="new-chat"
          onClick={newChat}
          aria-label={t('widget.new')}
          title={t('widget.new')}
          className="flex h-9 w-9 items-center justify-center rounded-full hover:bg-raised hover:text-ink"
        >
          <Icon name="edit" className="h-[18px] w-[18px]" />
        </button>
        <button
          type="button"
          data-testid="menu-button"
          data-menu-trigger
          aria-expanded={menuOpen}
          aria-controls="arif-menu"
          aria-label={t('widget.menu')}
          onClick={() => setMenuOpen((o) => !o)}
          className="flex h-9 w-9 items-center justify-center rounded-full hover:bg-raised hover:text-ink"
        >
          <Icon name="dots" />
        </button>
        <button
          type="button"
          data-testid="close-window"
          onClick={() => setWindowOpen(false)}
          aria-label={t('widget.close')}
          className="flex h-9 w-9 items-center justify-center rounded-full hover:bg-raised hover:text-ink"
        >
          <Icon name="close" className="h-[18px] w-[18px]" />
        </button>
      </div>
      <Menu open={menuOpen} onClose={closeMenu}>
        <MenuRow label={t('widget.view')}>
          <nav aria-label="views" className="flex rounded-full bg-raised p-0.5">
            {(['ask', 'compare', 'tasks'] as const).map((v) => (
              <a
                key={v}
                href={PATHS[v]}
                data-testid={`tab-${v}`}
                aria-current={view === v ? 'page' : undefined}
                onClick={(e) => {
                  e.preventDefault()
                  go(v)
                }}
                className={`flex-1 rounded-full px-2 py-1 text-center text-sm font-semibold no-underline ${view === v ? 'bg-surface text-ink shadow-card' : 'text-muted hover:text-ink'}`}
              >
                {t(`tab.${v}`)}
              </a>
            ))}
          </nav>
        </MenuRow>
        {config && provider && config.providers.length > 1 ? (
          <MenuRow label={t('widget.provider')}>
            <ProviderSwitch providers={config.providers} value={provider} onChange={setProvider} />
          </MenuRow>
        ) : null}
        <MenuRow label={t('widget.lang')}>
          <LangToggle />
        </MenuRow>
        <div className="grid gap-1 border-t border-line pt-2 text-[11px] leading-4 text-muted">
          <p data-testid="residency-badge" className="m-0">
            {t('footer.residency')}
          </p>
          <p data-testid="demo-notice" className="m-0">
            {t('notice.demo')}
          </p>
        </div>
      </Menu>
    </header>
  )

  const welcome = (
    <div className="grid gap-1">
      <p className="m-0 text-sm text-muted">{t('widget.hello')}</p>
      <h2 className="m-0 text-xl font-semibold leading-snug text-ink">{doc ? t('widget.help') : t('widget.helpNoDoc')}</h2>
    </div>
  )

  const conversation = (
    <>
      {earlier.length ? (
        <section aria-labelledby="history-title" data-testid="history" className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-1.5">
          <h3 id="history-title" className="m-0 text-xs font-normal text-muted">
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
                className="max-w-full truncate rounded-full border border-line px-3 py-1 text-xs text-ink hover:bg-raised"
              >
                <bdi>{q}</bdi>
              </button>
            ))}
          </div>
        </section>
      ) : null}
      {state.phase === 'idle' ? (
        doc ? (
          <>
            {welcome}
            <SuggestionGrid suggestions={suggestions} loading={suggestionsLoading} disabled={!canAsk} onPick={(q) => run(q, textOnly)} />
          </>
        ) : null
      ) : (
        <div ref={turnRef} className="min-w-0 scroll-mt-4">
          <Turn question={state.question} note={t(state.agent ? 'widget.noteAgent' : last?.textOnly ? 'widget.noteText' : 'widget.note')}>
            <AnswerView state={state} onRetry={last ? () => run(last.question, last.textOnly) : undefined} />
          </Turn>
        </div>
      )}
    </>
  )

  return (
    <AppContext.Provider value={ctx}>
      <div className="relative min-h-dvh overflow-hidden bg-bg text-ink">
        {/* A quiet workspace behind the window, so it reads as Arif floating over a page. */}
        <div aria-hidden className="pointer-events-none absolute inset-0 hidden sm:block">
          <div className="h-14 border-b border-line bg-surface/70" />
          <div className="absolute bottom-0 start-0 top-14 grid w-16 content-start justify-items-center gap-4 border-e border-line bg-surface/70 pt-5">
            {Array.from({ length: 8 }, (_, i) => (
              <span key={i} className="h-7 w-7 rounded-lg bg-sunken" />
            ))}
          </div>
        </div>

        {windowOpen ? (
          <div
            data-testid="arif-window"
            className={`relative mx-auto flex h-dvh w-full flex-col overflow-hidden bg-surface sm:my-[3vh] sm:h-[94vh] sm:max-h-[960px] sm:rounded-[22px] sm:border sm:border-line sm:shadow-float ${view === 'compare' ? 'sm:w-[min(1100px,calc(100%-2rem))]' : 'sm:w-[min(720px,calc(100%-2rem))]'}`}
          >
            {header}
            <DocBar
              docs={docs}
              activeId={currentId}
              busy={uploading}
              onAdd={(files) => void addFiles(files)}
              onSelect={select}
              onDelete={(id) => void remove(id)}
            />
            <main className="grid min-h-0 flex-1 grid-cols-[minmax(0,1fr)] content-start gap-5 overflow-y-auto px-4 py-5 sm:px-6">
              {uploadError ? (
                <p role="alert" data-testid="upload-error" className="m-0 rounded-xl bg-bad-soft px-3 py-2 text-xs text-bad">
                  {t('upload.error')}: <bdi>{uploadError}</bdi>
                </p>
              ) : null}
              {doc?.status === 'reading' ? <p className="m-0 text-xs font-semibold text-warn">{t('docs.readingLong')}</p> : null}
              {doc ? <Warnings items={doc.warnings} /> : null}
              {!doc && view !== 'tasks' ? (
                <>
                  {welcome}
                  <label
                    htmlFor={FILE_INPUT_ID}
                    data-testid="drop-zone"
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={(e) => {
                      e.preventDefault()
                      void addFiles(Array.from(e.dataTransfer.files))
                    }}
                    className="grid cursor-pointer justify-items-center gap-2 rounded-2xl border-[1.5px] border-dashed border-accent-line bg-raised px-4 py-10 text-center hover:border-accent"
                  >
                    <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-accent-soft text-accent-strong">
                      <Icon name="file" />
                    </span>
                    <span className="text-sm font-semibold text-ink">{uploading ? t('upload.uploading') : t('widget.drop')}</span>
                    <span className="text-xs text-muted">{t('upload.hint', { mb: config?.max_upload_mb ?? 20, pages: config?.max_pages ?? 60 })}</span>
                  </label>
                </>
              ) : null}
              {view === 'tasks' ? (
                <TasksView />
              ) : view === 'ask' ? (
                conversation
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
            {view === 'ask' ? (
              <Composer
                key={doc?.doc_id ?? 'none'}
                disabled={!canAsk}
                busy={busy}
                textOnly={textOnly}
                onTextOnly={setTextOnly}
                onAsk={(q) => run(q, textOnly)}
                onStop={stop}
                onSettings={() => setMenuOpen((o) => !o)}
                above={
                  state.phase !== 'idle' ? (
                    <SuggestionChips suggestions={suggestions} disabled={!canAsk || busy} onPick={(q) => run(q, textOnly)} />
                  ) : null
                }
              />
            ) : null}
          </div>
        ) : (
          <button
            type="button"
            data-testid="open-window"
            onClick={() => setWindowOpen(true)}
            aria-label={t('widget.open')}
            className="fixed bottom-6 end-6 flex h-14 w-14 items-center justify-center rounded-full border border-line bg-surface shadow-float hover:scale-105"
          >
            <Logo className="h-8 w-8" />
          </button>
        )}

        {source && doc ? (
          <SourcePanel key={`${doc.doc_id}:${source.page}:${source.quote ?? ''}`} docId={doc.doc_id} req={source} onClose={() => setSource(null)} />
        ) : null}
      </div>
    </AppContext.Provider>
  )
}
