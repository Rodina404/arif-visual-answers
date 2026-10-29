import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { format } from '../lib/format'
import { I18nContext, type I18n, type Lang } from './context'
import ar from './ar.json'
import en from './en.json'

type Dict = Record<string, string>
const DICTS: Record<Lang, Dict> = { ar, en }
const STORAGE_KEY = 'arif.lang'

function readStoredLang(): Lang {
  try {
    const v = window.localStorage.getItem(STORAGE_KEY)
    return v === 'en' || v === 'ar' ? v : 'ar'
  } catch {
    return 'ar'
  }
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(readStoredLang)
  const [digits, setDigits] = useState<'latn' | 'arab'>('latn')
  const dir = lang === 'ar' ? 'rtl' : 'ltr'

  useEffect(() => {
    document.documentElement.lang = lang
    document.documentElement.dir = dir
    document.title = DICTS[lang]['app.title']
  }, [lang, dir])

  const setLang = useCallback((l: Lang) => {
    setLangState(l)
    try {
      window.localStorage.setItem(STORAGE_KEY, l)
    } catch {
      /* private mode: the choice just isn't remembered */
    }
  }, [])

  const value = useMemo<I18n>(() => {
    // Western digits by default so values match the English source quotes; DIGITS=arab is display-only.
    const locale = lang === 'ar' ? (digits === 'arab' ? 'ar-EG' : 'ar-EG-u-nu-latn') : 'en-US'
    return {
      lang,
      dir,
      setLang,
      setDigits,
      t: (key, vars) => format(DICTS[lang][key] ?? DICTS.en[key] ?? key, vars),
      num: (n, opts) => new Intl.NumberFormat(locale, opts).format(n),
    }
  }, [lang, dir, digits, setLang])

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

