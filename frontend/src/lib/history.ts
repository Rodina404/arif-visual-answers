/** Per-document question history, kept in this browser only (best-effort: private mode just forgets). */
const key = (docId: string) => `arif.history.${docId}`
const MAX = 12

export function loadHistory(docId: string): string[] {
  try {
    const v = JSON.parse(window.localStorage.getItem(key(docId)) ?? '[]')
    return Array.isArray(v) ? v.filter((x): x is string => typeof x === 'string') : []
  } catch {
    return []
  }
}

export function addToHistory(docId: string, question: string): string[] {
  const next = [question, ...loadHistory(docId).filter((q) => q !== question)].slice(0, MAX)
  try {
    window.localStorage.setItem(key(docId), JSON.stringify(next))
  } catch {
    /* not remembered */
  }
  return next
}

export function forgetHistory(docId: string): void {
  try {
    window.localStorage.removeItem(key(docId))
  } catch {
    /* nothing to forget */
  }
}
