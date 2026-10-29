import { HttpError } from './sse'

export interface DocWarning {
  code: string
  message: string
  pages?: number[]
}

export interface UploadedDoc {
  doc_id: string
  pages: number
  sha256: string
  filename: string
  status: 'reading' | 'ready'
  language: string
  is_demo: boolean
  ocr_pages: number[]
  created_at: number
  warnings: DocWarning[]
}

export type ProviderName = 'gemini' | 'groq'

export interface ProviderInfo {
  name: ProviderName
  model: string
  available: boolean
}

export interface PublicConfig {
  provider: ProviderName
  providers: ProviderInfo[]
  model: string
  digits: 'latn' | 'arab'
  mock: boolean
  max_upload_mb: number
  max_pages: number
}

let fallbackId: string | null = null

/** This browser's random id: the server lists and deletes documents only for their owner. */
export function clientId(): string {
  try {
    let id = window.localStorage.getItem('arif.client')
    if (!id) {
      id = crypto.randomUUID()
      window.localStorage.setItem('arif.client', id)
    }
    return id
  } catch {
    fallbackId ??= crypto.randomUUID()
    return fallbackId
  }
}

const owned = (init: RequestInit = {}): RequestInit => ({ ...init, headers: { ...(init.headers ?? {}), 'X-Client-Id': clientId() } })

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let code = 'HTTP_ERROR'
    let message = res.statusText
    try {
      const j = (await res.json()) as { code?: string; message?: string }
      code = j.code ?? code
      message = j.message ?? message
    } catch {
      /* not JSON */
    }
    throw new HttpError(res.status, code, message)
  }
  return (await res.json()) as T
}

export async function uploadDocument(file: File): Promise<UploadedDoc> {
  const form = new FormData()
  form.append('file', file, file.name)
  return json<UploadedDoc>(await fetch('/api/documents', owned({ method: 'POST', body: form })))
}

export async function getPage(docId: string, page: number): Promise<{ page: number; text: string; has_text: boolean }> {
  return json(await fetch(`/api/documents/${encodeURIComponent(docId)}/pages/${page}`))
}

export async function getConfig(): Promise<PublicConfig> {
  return json(await fetch('/api/config'))
}

export async function listDocuments(): Promise<UploadedDoc[]> {
  return json(await fetch('/api/documents', owned()))
}

export async function getDocument(docId: string): Promise<UploadedDoc> {
  return json(await fetch(`/api/documents/${encodeURIComponent(docId)}`, owned()))
}

export async function deleteDocument(docId: string): Promise<void> {
  await json(await fetch(`/api/documents/${encodeURIComponent(docId)}`, owned({ method: 'DELETE' })))
}

export async function getSuggestions(docId: string, lang: string): Promise<{ questions: string[]; generated: boolean }> {
  return json(await fetch(`/api/documents/${encodeURIComponent(docId)}/suggestions?lang=${lang}`))
}
