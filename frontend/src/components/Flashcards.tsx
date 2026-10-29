import { useState } from 'react'
import type { FlashcardsProps } from '../catalog/schemas'
import { useI18n } from '../i18n/context'
import { stripUrls } from '../lib/text'
import type { Verification } from '../state/useAnswer'
import { Card } from './Card'
import { CitationChip } from './CitationChip'

function FlipCard({ card }: { card: FlashcardsProps['cards'][number] }) {
  const { t } = useI18n()
  const [flipped, setFlipped] = useState(false)
  return (
    <div className="flex flex-col gap-1">
      {/* A real button: Enter and Space flip it natively. */}
      <button
        type="button"
        data-testid="flashcard"
        aria-pressed={flipped}
        aria-label={`${t('cards.flip')}: ${stripUrls(card.front)}`}
        onClick={() => setFlipped((f) => !f)}
        className={`flex min-h-28 w-full flex-col justify-center rounded-xl border p-3 text-start transition-colors ${
          flipped ? 'border-accent bg-accent-soft' : 'border-line bg-raised hover:border-accent'
        }`}
      >
        <span className="mb-1 text-xs font-semibold text-muted">{flipped ? t('cards.back') : t('cards.front')}</span>
        <span dir="auto" data-testid="flashcard-text" className={`text-ink ${flipped ? 'text-sm leading-6' : 'text-base font-semibold'}`}>
          <bdi>{stripUrls(flipped ? card.back : card.front)}</bdi>
        </span>
      </button>
      {flipped && card.page ? (
        <span className="text-xs">
          <CitationChip page={card.page} />
        </span>
      ) : null}
    </div>
  )
}

export function Flashcards({ props, verification }: { props: FlashcardsProps; verification?: Verification }) {
  const { t } = useI18n()
  return (
    <Card lang={props.lang} type="flashcards" title={props.title} verification={verification}>
      <p className="mb-2 mt-0 text-xs text-muted">{t('cards.hint')}</p>
      <div className="grid gap-2" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(min(100%, 12rem), 1fr))' }}>
        {props.cards.map((c, i) => (
          <FlipCard key={i} card={c} />
        ))}
      </div>
    </Card>
  )
}
