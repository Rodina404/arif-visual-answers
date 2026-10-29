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
        <header data-testid="app-header" className="sticky top-0 z-30 bg-bg/90 backdrop-blur">
          <div className="mx-auto flex max-w-[760px] flex-wrap items-center justify-between gap-x-3 gap-y-2 px-4 py-3">
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

        <main className="mx-auto grid max-w-[760px] grid-cols-[minmax(0,1fr)] gap-6 px-4 pb-8 pt-2">
          <UploadPanel doc={doc} onUploaded={setDoc} limits={{ mb: config?.max_upload_mb ?? 20, pages: config?.max_pages ?? 60 }} />
          {view === 'ask' ? (
            <>
              <QuestionBox disabled={!doc} busy={busy} onAsk={run} onStop={stop} />
              {state.phase === 'idle' ? (
                <p className="m-0 py-6 text-center text-sm text-muted">{t('answer.empty')}</p>
              ) : (
                <AnswerView state={state} onRetry={last ? () => run(last.question, last.textOnly) : undefined} />
              )}
            </>
          ) : (
            <BeforeAfter docId={doc?.doc_id ?? null} provider={provider ?? undefined} />
          )}
        </main>

        <footer className="mx-auto grid max-w-[760px] gap-1 px-4 pb-10 pt-2 text-xs text-muted">
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
