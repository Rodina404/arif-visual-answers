import { useCallback, useEffect, useMemo, useState } from 'react'
import { getConfig, type ProviderName, type PublicConfig, type UploadedDoc } from './api/client'
import { AnswerView } from './components/AnswerView'
import { BeforeAfter } from './components/BeforeAfter'
import { LangToggle } from './components/LangToggle'
import { ProviderSwitch } from './components/ProviderSwitch'
import { QuestionBox } from './components/QuestionBox'
import { SourcePanel } from './components/SourcePanel'
import { UploadPanel } from './components/UploadPanel'
import { useI18n } from './i18n/context'
import { AppContext, type SourceRequest } from './state/context'
import { useAnswer } from './state/useAnswer'

type View = 'ask' | 'compare'
const PROVIDER_KEY = 'arif.provider'

function storedProvider(): ProviderName | null {
  try {
    const v = window.localStorage.getItem(PROVIDER_KEY)
    return v === 'gemini' || v === 'groq' ? v : null
  } catch {
    return null
  }
}
const viewFromPath = (): View => (window.location.pathname.replace(/\/+$/, '') === '/compare' ? 'compare' : 'ask')

export default function App() {
  const { t, lang, setDigits } = useI18n()
  const [view, setView] = useState<View>(viewFromPath)
  const [doc, setDoc] = useState<UploadedDoc | null>(null)
  const [config, setConfig] = useState<PublicConfig | null>(null)
  const [source, setSource] = useState<SourceRequest | null>(null)
  const [last, setLast] = useState<{ question: string; textOnly: boolean } | null>(null)
  const [provider, setProviderState] = useState<ProviderName | null>(storedProvider)
  const { state, ask, stop } = useAnswer()

  useEffect(() => {
    getConfig()
      .then((c) => {
        setConfig(c)
        setDigits(c.digits)
        // Keep a remembered choice only if that provider is usable on this server.
        setProviderState((p) => (p && c.providers.some((x) => x.name === p && x.available) ? p : c.provider))
      })
      .catch(() => setConfig(null))
  }, [setDigits])

  useEffect(() => {
    const onPop = () => setView(viewFromPath())
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])

  const go = (v: View) => {
    setView(v)
    window.history.pushState(null, '', v === 'compare' ? '/compare' : '/')
  }

  const setProvider = (p: ProviderName) => {
    setProviderState(p)
    try {
      window.localStorage.setItem(PROVIDER_KEY, p)
    } catch {
      /* not remembered in private mode */
    }
  }

  const run = useCallback(
    (question: string, textOnly: boolean) => {
      if (!doc) return
      setLast({ question, textOnly })
      void ask({ docId: doc.doc_id, question, lang, textOnly, provider: provider ?? undefined })
    },
    [doc, ask, lang, provider],
  )

  const ctx = useMemo(() => ({ docId: doc?.doc_id ?? null, openSource: setSource }), [doc])
  const busy = state.phase === 'thinking' || state.phase === 'streaming'

  return (
    <AppContext.Provider value={ctx}>
      <div className="min-h-screen bg-bg text-ink">
        <header data-testid="app-header" className="border-b border-line bg-surface">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3">
            <div data-testid="brand" className="min-w-0">
              <h1 className="m-0 text-lg font-semibold leading-tight">{t('app.title')}</h1>
              <p className="m-0 text-xs text-muted">{t('app.subtitle')}</p>
            </div>
            <nav aria-label="views" className="flex flex-wrap items-center gap-2">
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
                  className={`rounded-lg px-3 py-1.5 text-sm font-semibold no-underline ${view === v ? 'bg-accent-soft text-accent' : 'text-muted hover:text-ink'}`}
                >
                  {t(`tab.${v}`)}
                </a>
              ))}
              {config && provider ? (
                <ProviderSwitch providers={config.providers} value={provider} onChange={setProvider} />
              ) : null}
              <LangToggle />
            </nav>
          </div>
        </header>

        <main className="mx-auto grid max-w-6xl gap-4 px-4 py-5">
          <p data-testid="demo-notice" className="m-0 text-xs text-muted">
            {t('notice.demo')}
            {config?.mock ? <> · {t('notice.mock')}</> : null}
          </p>
          <UploadPanel
            doc={doc}
            onUploaded={setDoc}
            limits={{ mb: config?.max_upload_mb ?? 20, pages: config?.max_pages ?? 60 }}
          />
          {view === 'ask' ? (
            <div className="mx-auto grid w-full max-w-3xl gap-5">
              <div className="rounded-2xl border border-line bg-surface p-4">
                <QuestionBox disabled={!doc} busy={busy} onAsk={run} onStop={stop} />
              </div>
              {state.phase === 'idle' ? (
                <p className="m-0 text-center text-sm text-muted">{t('answer.empty')}</p>
              ) : (
                <AnswerView state={state} onRetry={last ? () => run(last.question, last.textOnly) : undefined} />
              )}
            </div>
          ) : (
            <BeforeAfter docId={doc?.doc_id ?? null} provider={provider ?? undefined} />
          )}
        </main>

        <footer className="mx-auto max-w-6xl px-4 pb-8 pt-2">
          <p data-testid="residency-badge" className="m-0 inline-block rounded-full border border-line bg-surface px-3 py-1 text-xs text-muted">
            {t('footer.residency')}
          </p>
        </footer>

        {source && doc ? (
          <SourcePanel key={`${doc.doc_id}:${source.page}:${source.quote ?? ''}`} docId={doc.doc_id} req={source} onClose={() => setSource(null)} />
        ) : null}
      </div>
    </AppContext.Provider>
  )
}
