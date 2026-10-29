import { useEffect, useRef, type ReactNode } from 'react'
import { useI18n } from '../i18n/context'

/** The options popover under the header: view, model and language, plus the demo notices. Stays mounted. */
export function Menu({ open, onClose, children }: { open: boolean; onClose: () => void; children: ReactNode }) {
  const { t } = useI18n()
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const onDown = (e: PointerEvent) => {
      const target = e.target as Element | null
      if (ref.current?.contains(target) || target?.closest('[data-menu-trigger]')) return
      onClose()
    }
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    document.addEventListener('pointerdown', onDown)
    window.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('pointerdown', onDown)
      window.removeEventListener('keydown', onKey)
    }
  }, [open, onClose])
  return (
    <div
      ref={ref}
      id="arif-menu"
      data-testid="menu"
      role="dialog"
      aria-label={t('widget.settings')}
      hidden={!open}
      className="absolute end-3 top-14 z-40 grid w-72 max-w-[calc(100%-1.5rem)] gap-3 rounded-2xl border border-line bg-surface p-3 shadow-float"
    >
      {children}
    </div>
  )
}

export function MenuRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid gap-1.5">
      <span className="text-[11px] font-semibold text-muted">{label}</span>
      {children}
    </div>
  )
}
