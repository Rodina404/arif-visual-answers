/** Skeletons shaped like the planned component (band + body), so the layout doesn't jump when it arrives. */
export function Skeleton({ type }: { type: string }) {
  let body
  switch (type) {
    case 'chart':
      body = (
        <>
          <div className="grid grid-cols-3 gap-2">
            {[0, 1, 2].map((i) => (
              <div key={i} className="skeleton h-14" />
            ))}
          </div>
          <div className="flex h-44 items-end gap-3 px-2">
            {[40, 65, 30, 85, 55].map((h, i) => (
              <div key={i} className="skeleton flex-1" style={{ height: `${h}%` }} />
            ))}
          </div>
        </>
      )
      break
    case 'comparison':
      body = (
        <div className="grid grid-cols-2 gap-3">
          <div className="skeleton h-40" />
          <div className="skeleton h-40" />
        </div>
      )
      break
    case 'quiz':
      body = (
        <div className="grid grid-cols-2 gap-2">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="skeleton h-16" />
          ))}
        </div>
      )
      break
    case 'flashcards':
      body = (
        <div className="grid grid-cols-3 gap-2">
          {Array.from({ length: 6 }, (_, i) => (
            <div key={i} className="skeleton h-28" />
          ))}
        </div>
      )
      break
    case 'diagram':
      body = (
        <div className="flex items-center justify-center gap-4 py-6">
          {[0, 1, 2].map((i) => (
            <div key={i} className="skeleton h-14 w-28" />
          ))}
        </div>
      )
      break
    default:
      body = (
        <div className="grid gap-3">
          {[90, 78, 66].map((w) => (
            <div key={w} className="skeleton h-5" style={{ width: `${w}%` }} />
          ))}
        </div>
      )
  }
  return (
    <div data-testid="skeleton" data-skeleton-type={type} aria-hidden className="overflow-hidden rounded-2xl bg-surface shadow-card">
      <div className="h-7 opacity-60" style={{ background: `var(--color-band-${type}, var(--color-band-text))` }} />
      <div className="grid gap-3 p-4 sm:p-5">
        <div className="skeleton h-5 w-1/2" />
        {body}
      </div>
    </div>
  )
}
