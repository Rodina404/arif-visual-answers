/**
 * Zod mirror of backend/app/catalog.py. Hand-written; `npm run test:schemas` checks it against the
 * exported Pydantic schema (src/catalog/schema.json) so the two cannot drift apart.
 */
import { z } from 'zod'

const s = (max: number, min = 0) => z.string().min(min).max(max)
const page = z.number().int().min(1)

export const Lang = z.enum(['ar', 'en'])
export const Citation = z.strictObject({ page, quote: s(300, 10) })

const base = {
  id: z.string().regex(/^c[1-9]$/),
  lang: Lang,
  title: s(80),
  reason: s(140),
}

export const TextComponent = z.strictObject({ ...base, type: z.literal('text'), body: s(1200) })

export const ChartPoint = z.strictObject({ label: s(30), value: z.number(), citation: Citation })
export const ChartSeries = z.strictObject({ name: s(40), points: z.array(ChartPoint).min(3).max(12) })
export const ChartComponent = z.strictObject({
  ...base,
  type: z.literal('chart'),
  chart_type: z.enum(['bar', 'line']),
  x_label: s(40),
  y_label: s(40),
  unit: s(12),
  series: z.array(ChartSeries).min(1).max(2),
})

export const Attribute = z.strictObject({ key: s(30), value: s(80), citation: Citation.optional() })
export const ComparisonItem = z.strictObject({
  name: s(40),
  summary: s(160),
  attributes: z.array(Attribute).min(2).max(6),
})
export const ComparisonComponent = z.strictObject({
  ...base,
  type: z.literal('comparison'),
  items: z.array(ComparisonItem).min(2).max(4),
})

export const Step = z.strictObject({ title: s(60), detail: s(220), page: page.optional() })
export const StepsComponent = z.strictObject({
  ...base,
  type: z.literal('steps'),
  ordered: z.literal(true),
  steps: z.array(Step).min(2).max(8),
})

export const TableRow = z.strictObject({ cells: z.array(s(60)), citation: Citation })
export const TableComponent = z
  .strictObject({
    ...base,
    type: z.literal('table'),
    columns: z.array(s(30)).min(2).max(6),
    rows: z.array(TableRow).min(2).max(12),
  })
  .refine((t) => t.rows.every((r) => r.cells.length === t.columns.length), 'cells must match columns')

export const DiagramNode = z.strictObject({ id: s(20, 1), label: s(40) })
export const DiagramEdge = z.strictObject({ from: s(20), to: s(20), label: s(24).optional() })
export const DiagramComponent = z
  .strictObject({
    ...base,
    type: z.literal('diagram'),
    layout: z.enum(['flow', 'cycle']),
    nodes: z.array(DiagramNode).min(2).max(10),
    edges: z.array(DiagramEdge).min(1).max(14),
    page: page.optional(),
  })
  .refine((d) => {
    const ids = new Set(d.nodes.map((n) => n.id))
    return ids.size === d.nodes.length && d.edges.every((e) => ids.has(e.from) && ids.has(e.to))
  }, 'edges must reference nodes')

export const FormulaComponent = z.strictObject({
  ...base,
  type: z.literal('formula'),
  latex: s(300, 1),
  explanation: s(220),
  citation: Citation.optional(),
})

export const QuizQuestion = z
  .strictObject({
    prompt: s(160),
    options: z.array(s(80)).min(3).max(4),
    correct_index: z.number().int().min(0).max(3),
    explanation: s(220),
    citation: Citation,
  })
  .refine((q) => q.correct_index < q.options.length, 'correct_index out of range')
export const QuizComponent = z.strictObject({
  ...base,
  type: z.literal('quiz'),
  questions: z.array(QuizQuestion).min(1).max(4),
})

export const Flashcard = z.strictObject({ front: s(60), back: s(200), page: page.optional() })
export const FlashcardsComponent = z.strictObject({
  ...base,
  type: z.literal('flashcards'),
  cards: z.array(Flashcard).min(3).max(8),
})

// Agent components: built by the server from tool results (never by the model's answer schema).
export const TaskItem = z.strictObject({ title: s(120, 1), owner: s(60, 1), due_date: s(40).optional(), citation: Citation })
export const TaskCardsComponent = z.strictObject({
  ...base,
  type: z.literal('task_cards'),
  tasks: z.array(TaskItem).min(1).max(8),
})

export const DecisionItem = z.strictObject({ text: s(200, 1), citation: Citation })
export const DecisionCardsComponent = z.strictObject({
  ...base,
  type: z.literal('decision_cards'),
  decisions: z.array(DecisionItem).min(1).max(8),
})

export const ActionFlag = z.enum(['UNVERIFIED_SOURCE', 'FROM_HIDDEN_TEXT', 'NOT_REQUESTED'])
export const ProposedAction = z.strictObject({
  proposal_id: z.string().regex(/^p[0-9a-f]{12}$/),
  kind: z.enum(['create_task', 'draft_message']),
  title: s(120, 1),
  owner: s(60).optional(),
  due_date: s(40).optional(),
  to: s(120).optional(),
  body: s(1200).optional(),
  citation: Citation.optional(),
  flags: z.array(ActionFlag).max(3).optional(),
})
export const ActionCardComponent = z.strictObject({
  ...base,
  type: z.literal('action_card'),
  actions: z.array(ProposedAction).min(1).max(6),
})

export const COMPONENT_SCHEMAS = {
  text: TextComponent,
  chart: ChartComponent,
  comparison: ComparisonComponent,
  steps: StepsComponent,
  table: TableComponent,
  diagram: DiagramComponent,
  formula: FormulaComponent,
  quiz: QuizComponent,
  flashcards: FlashcardsComponent,
  task_cards: TaskCardsComponent,
  decision_cards: DecisionCardsComponent,
  action_card: ActionCardComponent,
} as const

/** Types the agent produces; they never lead the answer as a headline. */
export const AGENT_TYPES = new Set<string>(['task_cards', 'decision_cards', 'action_card'])

export type ComponentType = keyof typeof COMPONENT_SCHEMAS
export type CitationT = z.infer<typeof Citation>
export type TextProps = z.infer<typeof TextComponent>
export type ChartProps = z.infer<typeof ChartComponent>
export type ComparisonProps = z.infer<typeof ComparisonComponent>
export type StepsProps = z.infer<typeof StepsComponent>
export type TableProps = z.infer<typeof TableComponent>
export type DiagramProps = z.infer<typeof DiagramComponent>
export type FormulaProps = z.infer<typeof FormulaComponent>
export type QuizProps = z.infer<typeof QuizComponent>
export type FlashcardsProps = z.infer<typeof FlashcardsComponent>
export type TaskCardsProps = z.infer<typeof TaskCardsComponent>
export type DecisionCardsProps = z.infer<typeof DecisionCardsComponent>
export type ActionCardProps = z.infer<typeof ActionCardComponent>
export type ProposedActionT = z.infer<typeof ProposedAction>

export function isComponentType(t: string): t is ComponentType {
  return Object.hasOwn(COMPONENT_SCHEMAS, t)
}
