import { lazy, Suspense } from 'react'
import type { Stat } from '../lib/keyNumbers'

// motion (CountUp's engine) loads only when a number is shown; the final value renders meanwhile.
const CountUp = lazy(() => import('./bits/CountUp'))

/** A signed number that counts up once when it scrolls into view (instant with reduced motion). */
export function StatNumber({ stat, className }: { stat: Stat; className?: string }) {
  const sign = stat.kind === 'gap' && stat.value > 0 ? '+' : ''
  const final = `${sign}${stat.value.toFixed(stat.decimals)}`
  return (
    <bdi className={className} data-testid="stat-value" data-value={stat.value}>
      <Suspense fallback={<span className="tabular-nums">{final}</span>}>
        <CountUp to={stat.value} from={0} decimals={stat.decimals} duration={1.1} prefix={sign} />
      </Suspense>
    </bdi>
  )
}
