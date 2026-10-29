import { useCallback, useReducer, useRef } from 'react'
import { HttpError, streamSSE, type SSEEvent } from '../api/sse'
import { COMPONENT_SCHEMAS, isComponentType, type ComponentType } from '../catalog/schemas'
import type { ProviderName } from '../api/client'
import type { Lang } from '../i18n/context'

export interface Verification {
  status: 'verified' | 'partial' | 'unverified'
  dropped_points: number
}

export type Slot =
  | { id: string; type: string; state: 'planned' }
  | { id: string; type: ComponentType; state: 'ready'; props: unknown; verification: Verification; downgradedFrom?: string }
  | { id: string; type: string; state: 'dropped'; reason: string; fallbackText?: string }

export interface Warning {
  code: string
  message: string
  pages?: number[]
}

export interface Metrics {
  mode: string
  model: string
  provider: string
  thinking_level: string
  tokens: { input: number; cached_input: number; output: number; thinking: number; total: number }
  cost_usd: { input: number; cached_input: number; output: number; total: number; price_table_date: string }
  latency_ms: { ttft_text: number | null; first_component: number | null; total: number }
  components: { emitted: number; dropped: number; verified: number; partial: number; unverified: number }
  cache: { app_cache_hit: boolean; gemini_cached_tokens: number }
  schema_mode: string
  fallback_used: boolean
  retrieval?: {
    retrieval: 'bm25' | 'off'
    pages?: number[]
    chunks?: number
    context_tokens_est?: number
    prompt_budget?: number
    streamed?: boolean
  }
}

export interface AnswerState {
  phase: 'idle' | 'thinking' | 'streaming' | 'done' | 'error'
  question: string
  lang: Lang
  text: string
  slots: Slot[]
  warnings: Warning[]
  metrics?: Metrics
  error?: { code: string; message: string; status?: number }
  cached: boolean
  startedAt: number
}

const initial: AnswerState = {
  phase: 'idle',
  question: '',
  lang: 'ar',
  text: '',
  slots: [],
  warnings: [],
  cached: false,
  startedAt: 0,
}

// Drops the user should hear about. Silent ones are policy decisions (restraint), not failures.
const SILENT_DROPS = new Set([
  'unknown_type',
  'too_many_components',
  'needs_visual_false',
  'only_one_quiz',
  'duplicate_id',
  'empty_reason',
])

type Action =
  | { kind: 'start'; question: string; lang: Lang }
  | { kind: 'event'; ev: SSEEvent }
  | { kind: 'fail'; code: string; message: string; status?: number }
  | { kind: 'reset' }

function upsert(slots: Slot[], slot: Slot): Slot[] {
  const i = slots.findIndex((s) => s.id === slot.id)
  if (i < 0) return [...slots, slot]
  const next = slots.slice()
  next[i] = slot
  return next
}

function reduce(state: AnswerState, a: Action): AnswerState {
  if (a.kind === 'reset') return initial
  if (a.kind === 'start') return { ...initial, phase: 'thinking', question: a.question, lang: a.lang, startedAt: performance.now() }
  if (a.kind === 'fail') return { ...state, phase: 'error', error: { code: a.code, message: a.message, status: a.status } }

  const { event, data } = a.ev
  const d = data as Record<string, unknown>
  switch (event) {
    case 'RUN_STARTED':
      return { ...state, cached: Boolean(d.cached) }
    case 'TEXT_MESSAGE_CONTENT':
      return { ...state, phase: 'streaming', text: state.text + String(d.delta ?? '') }
    case 'COMPONENT_PLANNED': {
      const type = String(d.type)
      if (!isComponentType(type)) return state
      return { ...state, phase: 'streaming', slots: upsert(state.slots, { id: String(d.component_id), type, state: 'planned' }) }
    }
    case 'COMPONENT': {
      const id = String(d.component_id)
      const type = String(d.type)
      if (!isComponentType(type)) {
        return { ...state, slots: state.slots.filter((s) => s.id !== id) }
      }
      // The server already validated it; validate again so a protocol bug can't reach a renderer.
      const parsed = COMPONENT_SCHEMAS[type].safeParse(d.props)
      if (!parsed.success) {
        return { ...state, slots: upsert(state.slots, { id, type, state: 'dropped', reason: 'invalid_props' }) }
      }
      const slot: Slot = {
        id,
        type,
        state: 'ready',
        props: parsed.data,
        verification: d.verification as Verification,
        downgradedFrom: typeof d.downgraded_from === 'string' ? d.downgraded_from : undefined,
      }
      // Components arrive in display order; move this one after any already-ready slots.
      const others = state.slots.filter((s) => s.id !== id)
      const lastReady = others.map((s) => s.state).lastIndexOf('ready')
      const next = [...others.slice(0, lastReady + 1), slot, ...others.slice(lastReady + 1)]
      return { ...state, phase: 'streaming', slots: next }
    }
    case 'COMPONENT_DROPPED': {
      const id = String(d.component_id)
      const reason = String(d.reason)
      if (SILENT_DROPS.has(reason)) return { ...state, slots: state.slots.filter((s) => s.id !== id) }
      const slot: Slot = {
        id,
        type: String(d.type),
        state: 'dropped',
        reason,
        fallbackText: typeof d.fallback_text === 'string' ? d.fallback_text : undefined,
      }
      return { ...state, slots: upsert(state.slots, slot) }
    }
    case 'WARNING':
      if (state.warnings.some((w) => w.code === d.code)) return state
      return { ...state, warnings: [...state.warnings, d as unknown as Warning] }
    case 'METRICS':
      return { ...state, metrics: d as unknown as Metrics }
    case 'RUN_ERROR':
      return {
        ...state,
        phase: 'error',
        slots: state.slots.filter((s) => s.state !== 'planned'),
        error: { code: String(d.code), message: String(d.message) },
      }
    case 'RUN_FINISHED':
      return { ...state, phase: 'done', slots: state.slots.filter((s) => s.state !== 'planned') }
    default:
      return state
  }
}

export interface AskOptions {
  docId: string
  question: string
  lang: Lang
  textOnly?: boolean
  provider?: ProviderName
  endpoint?: '/api/ask' | '/api/ask_text'
}

export function useAnswer() {
  const [state, dispatch] = useReducer(reduce, initial)
  const abort = useRef<AbortController | null>(null)

  const ask = useCallback(async (o: AskOptions) => {
    abort.current?.abort()
    const ctrl = new AbortController()
    abort.current = ctrl
    dispatch({ kind: 'start', question: o.question, lang: o.lang })
    try {
      await streamSSE(
        o.endpoint ?? '/api/ask',
        { doc_id: o.docId, question: o.question, lang: o.lang, text_only: Boolean(o.textOnly), provider: o.provider },
        (ev) => dispatch({ kind: 'event', ev }),
        { signal: ctrl.signal },
      )
    } catch (err) {
      if (ctrl.signal.aborted) return
      if (err instanceof HttpError) dispatch({ kind: 'fail', code: err.code, message: err.message, status: err.status })
      else dispatch({ kind: 'fail', code: 'NETWORK', message: String(err) })
    }
  }, [])

  const stop = useCallback(() => abort.current?.abort(), [])
  const reset = useCallback(() => {
    abort.current?.abort()
    dispatch({ kind: 'reset' })
  }, [])

  return { state, ask, stop, reset }
}

export { reduce as answerReducer }
