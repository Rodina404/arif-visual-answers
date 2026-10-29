import { lazy, type ComponentType as ReactComponent } from 'react'
import { ActionCard, DecisionCards, TaskCards } from '../components/AgentCards'
import { ComparisonCard } from '../components/ComparisonCard'
import { DataTable } from '../components/DataTable'
import { DiagramView } from '../components/DiagramView'
import { Flashcards } from '../components/Flashcards'
import { QuizCard } from '../components/QuizCard'
import { StepCards } from '../components/StepCards'
import { TextBlock } from '../components/TextBlock'
import type { Verification } from '../state/useAnswer'
import type { ComponentType } from './schemas'

export interface RendererProps {
  props: never
  verification?: Verification
  downgradedFrom?: string
}

// Recharts and KaTeX are most of the bundle; load them only when an answer needs them.
// (Fast-refresh hint only: these lazy wrappers never need hot reloading.)
// oxlint-disable-next-line react/only-export-components
const ChartCard = lazy(() => import('../components/ChartCard').then((m) => ({ default: m.ChartCard })))
// oxlint-disable-next-line react/only-export-components
const FormulaCard = lazy(() => import('../components/FormulaCard').then((m) => ({ default: m.FormulaCard })))

/** type -> pure props-in renderer. Types not listed here are ignored by the answer view. */
export const REGISTRY: Record<ComponentType, ReactComponent<RendererProps>> = {
  text: TextBlock as ReactComponent<RendererProps>,
  chart: ChartCard as ReactComponent<RendererProps>,
  comparison: ComparisonCard as ReactComponent<RendererProps>,
  steps: StepCards as ReactComponent<RendererProps>,
  table: DataTable as ReactComponent<RendererProps>,
  diagram: DiagramView as ReactComponent<RendererProps>,
  formula: FormulaCard as ReactComponent<RendererProps>,
  quiz: QuizCard as ReactComponent<RendererProps>,
  flashcards: Flashcards as ReactComponent<RendererProps>,
  task_cards: TaskCards as ReactComponent<RendererProps>,
  decision_cards: DecisionCards as ReactComponent<RendererProps>,
  action_card: ActionCard as ReactComponent<RendererProps>,
}
