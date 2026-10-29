export function fmtUsd(v: number): string {
  if (v === 0) return '$0'
  return v < 0.01 ? `$${v.toFixed(4)}` : `$${v.toFixed(3)}`
}

export function format(template: string, vars?: Record<string, string | number>): string {
  if (!vars) return template
  return template.replace(/\{(\w+)\}/g, (m, k: string) => (k in vars ? String(vars[k]) : m))
}

export const DEMO_QUESTIONS = ['q1', 'q2', 'q3', 'q4', 'q5', 'q6'] as const

export function errorMessage(t: (k: string) => string, err?: { code: string; status?: number }): string {
  if (!err) return ''
  if (err.status === 429 || err.code === 'RATE_LIMITED') return t('error.rate')
  if (err.code === 'TIMEOUT') return t('error.timeout')
  if (err.code === 'NETWORK') return t('error.network')
  if (err.code === 'PROVIDER_UNAVAILABLE') return t('error.provider')
  return t('error.generic')
}
