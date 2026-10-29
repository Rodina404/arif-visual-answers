/** POST + fetch-stream SSE parser (EventSource only supports GET). */

export interface SSEEvent {
  event: string
  data: unknown
}

export class HttpError extends Error {
  status: number
  code: string
  constructor(status: number, code: string, message: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

export function parseBlock(block: string): SSEEvent | null {
  let event = 'message'
  const data: string[] = []
  for (const line of block.split(/\r?\n/)) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    else if (line.startsWith('data:')) data.push(line.slice(5).replace(/^ /, ''))
  }
  if (!data.length) return null
  try {
    return { event, data: JSON.parse(data.join('\n')) }
  } catch {
    return null
  }
}

export async function streamSSE(
  url: string,
  body: unknown,
  onEvent: (e: SSEEvent) => void,
  opts: { signal?: AbortSignal; headers?: Record<string, string> } = {},
): Promise<void> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream', ...opts.headers },
    body: JSON.stringify(body),
    signal: opts.signal,
  })
  if (!res.ok || !res.body) {
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
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader()
  let buf = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buf += value
    let idx: number
    while ((idx = buf.search(/\r?\n\r?\n/)) >= 0) {
      const block = buf.slice(0, idx)
      buf = buf.slice(idx).replace(/^\r?\n\r?\n/, '')
      const ev = parseBlock(block)
      if (ev) onEvent(ev)
    }
  }
  const tail = parseBlock(buf)
  if (tail) onEvent(tail)
}
