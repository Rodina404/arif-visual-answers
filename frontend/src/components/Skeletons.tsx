/** Skeletons shaped like the planned component, so the layout doesn't jump when it arrives. */
export function Skeleton({ type }: { type: string }) {
  const bars = (n: number, h = 'h-4') =>
    Array.from({ length: n }, (_, i) => <div key={i} className={`skeleton ${h}`} style={{ width: `${90 - i * 12}%` }} />)
  let body
  switch (type) {
    case 'chart':
      body = (
        <div className="flex h-52 items-end gap-3 px-2">
          {[40, 65, 30, 85, 55].map((h, i) => (
            <div key={i} className="skeleton flex-1" style={{ height: `${h}%` }} />
          ))}
        </div>
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
    case 'table':
      body = <div className="grid gap-2">{Array.from({ length: 5 }, (_, i) => <div key={i} className="skeleton h-7" />)}</div>
      break
    case 'steps':
    case 'quiz':
      body = <div className="grid gap-2">{Array.from({ length: 3 }, (_, i) => <div key={i} className="skeleton h-14" />)}</div>
      break
    case 'flashcards':
      body = <div className="grid grid-cols-3 gap-2">{Array.from({ length: 6 }, (_, i) => <div key={i} className="skeleton h-24" />)}</div>
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
      body = <div className="grid gap-2">{bars(3)}</div>
  }
  return (
    <div data-testid="skeleton" data-skeleton-type={type} aria-hidden className="rounded-2xl border border-line bg-surface p-4 sm:p-5">
      <div className="skeleton mb-4 h-5 w-1/2" />
      {body}
    </div>
  )
}
