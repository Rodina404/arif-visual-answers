import { createContext, useContext } from 'react'

export type Lang = 'ar' | 'en'

export interface I18n {
  lang: Lang
  dir: 'rtl' | 'ltr'
  setLang: (l: Lang) => void
  t: (key: string, vars?: Record<string, string | number>) => string
  num: (n: number, opts?: Intl.NumberFormatOptions) => string
  setDigits: (d: 'latn' | 'arab') => void
}

export const I18nContext = createContext<I18n | null>(null)

export function useI18n(): I18n {
  const v = useContext(I18nContext)
  if (!v) throw new Error('useI18n outside I18nProvider')
  return v
}
