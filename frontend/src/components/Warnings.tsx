import { useI18n } from '../i18n/context'

export interface WarningLike {
  code: string
  message: string
  pages?: number[]
}

export function Warnings({ items }: { items: WarningLike[] }) {
  const { t, num } = useI18n()
  if (!items.length) return null
  return (
    <div className="grid gap-2">
      {items.map((w) => {
        const pages = (w.pages ?? []).map((p) => num(p)).join('، ')
        const key = `warn.${w.code}`
        const text = t(key, { pages })
        return (
          <p
            key={w.code}
            role="alert"
            data-testid="warning"
            data-code={w.code}
            className="m-0 rounded-2xl bg-warn-soft px-4 py-2.5 text-sm text-warn"
          >
            <span aria-hidden className="me-1">⚠</span>
            {text === key ? w.message : text}
          </p>
        )
      })}
    </div>
  )
}
