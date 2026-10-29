/** Small line icons, one per component type (16×16, currentColor). */
const PATHS: Record<string, string> = {
  chart: 'M2.5 13.5h11M4 11V8m4 3V4m4 7V6.5',
  comparison: 'M2.5 3.5h4.5v9H2.5zM9 3.5h4.5v9H9z',
  steps: 'M5.5 4h8M5.5 8h8M5.5 12h8M2.5 4h.01M2.5 8h.01M2.5 12h.01',
  table: 'M2.5 3.5h11v9h-11zM2.5 7h11M2.5 10h11M7 3.5v9',
  diagram: 'M4 4.5a1.5 1.5 0 1 0 0 .01M12 4.5a1.5 1.5 0 1 0 0 .01M8 12a1.5 1.5 0 1 0 0 .01M5.2 5.6 7 10.6M10.8 5.6 9 10.6',
  formula: 'M12 3.5H4.5L8.5 8l-4 4.5H12',
  quiz: 'M6 6a2 2 0 1 1 2.8 1.8C8.3 8 8 8.5 8 9.2M8 12h.01M2.5 8a5.5 5.5 0 1 0 11 0 5.5 5.5 0 0 0-11 0',
  flashcards: 'M4.5 2.5h7a1 1 0 0 1 1 1v7m-10-5h7a1 1 0 0 1 1 1v6.5a1 1 0 0 1-1 1h-7a1 1 0 0 1-1-1V6.5a1 1 0 0 1 1-1',
  text: 'M3 4h10M3 7h10M3 10h7M3 13h5',
  task_cards: 'M2.5 4.5l1.5 1.5 2.5-2.5M8.5 5h5M2.5 10.5l1.5 1.5 2.5-2.5M8.5 11h5',
  decision_cards: 'M3.5 14V2.5M3.5 3h8l-1.5 2.5 1.5 2.5h-8',
  action_card: 'M8 2l5 2v4c0 3-2.2 5-5 6-2.8-1-5-3-5-6V4zM6 8l1.5 1.5L10.5 6.5',
}

export function TypeIcon({ type, className = 'h-4 w-4' }: { type: string; className?: string }) {
  return (
    <svg viewBox="0 0 16 16" className={className} fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d={PATHS[type] ?? PATHS.text} />
    </svg>
  )
}
