/** Model strings are data. Links are never rendered; scheme-bearing text is shown defanged. */
const URL_RE = /\b(?:https?|ftp|file|javascript|vbscript|data):\S*|\bwww\.\S+/gi

export function stripUrls(s: string): string {
  return s.replace(URL_RE, '[link]')
}

const ARABIC = /[؀-ۿ]/

export function isMostlyLatin(s: string): boolean {
  return !ARABIC.test(s)
}

/** Collapse whitespace for robust highlighting of a quote inside page text. */
export function findQuote(page: string, quote: string): [number, number] | null {
  const norm = (t: string) => t.replace(/[‐-―−�]/g, ' ')
  const p = norm(page)
  const words = norm(quote).trim().split(/\s+/).filter(Boolean)
  if (!words.length) return null
  const esc = words.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
  for (let take = esc.length; take >= Math.min(4, esc.length); take--) {
    const re = new RegExp(esc.slice(0, take).join('[\\s-]*'), 'i')
    const m = re.exec(p)
    if (m) {
      // Extend to the full quote length if the rest also matches from here.
      const full = new RegExp(esc.join('[\\s-]*'), 'i').exec(p.slice(m.index))
      return full && full.index === 0 ? [m.index, m.index + full[0].length] : [m.index, m.index + m[0].length]
    }
  }
  return null
}
