import { useEffect, useId, useRef, useState } from 'react'
import type { DiagramProps } from '../catalog/schemas'
import { useI18n } from '../i18n/context'
import { stripUrls } from '../lib/text'
import type { Verification } from '../state/useAnswer'
import { Card } from './Card'
import { CitationChip } from './CitationChip'

const NODE_W = 176
const NODE_H = 66
const GAP_X = 40
const GAP_Y = 58
const FONT = '"IBM Plex Sans Arabic", "Noto Sans Arabic", system-ui, sans-serif'

interface Box {
  x: number
  y: number
  w: number
  h: number
}

/** Split a label into at most 3 lines of ~22 characters on word boundaries. */
function wrap(label: string, max = 22): string[] {
  const lines: string[] = []
  let cur = ''
  for (const word of label.split(/\s+/)) {
    if ((cur + ' ' + word).trim().length > max && cur) {
      lines.push(cur)
      cur = word
    } else cur = (cur + ' ' + word).trim()
  }
  if (cur) lines.push(cur)
  return lines.slice(0, 3)
}

/** Snake layout: rows alternate direction so each row ends right above the next row's start. */
function flowLayout(n: number, rtl: boolean, maxPerRow: number): { boxes: Box[]; height: number; width: number } {
  const perRow = Math.min(maxPerRow, n)
  const rowW = perRow * NODE_W + (perRow - 1) * GAP_X
  const W = rowW + 32
  const x0 = 16
  const boxes: Box[] = []
  for (let i = 0; i < n; i++) {
    const row = Math.floor(i / perRow)
    let col = i % perRow
    const forward = row % 2 === 0 ? !rtl : rtl // reading direction on even rows
    if (!forward) col = perRow - 1 - col
    boxes.push({ x: x0 + col * (NODE_W + GAP_X), y: 16 + row * (NODE_H + GAP_Y), w: NODE_W, h: NODE_H })
  }
  const rows = Math.ceil(n / perRow)
  return { boxes, height: 32 + rows * NODE_H + (rows - 1) * GAP_Y, width: W }
}

/** Cycle layout: clockwise in LTR, counter-clockwise in RTL, starting at the top. */
function cycleLayout(n: number, rtl: boolean): { boxes: Box[]; height: number; width: number } {
  const r = n <= 4 ? 120 : 150
  const W = 640
  const cx = W / 2
  const cy = r + NODE_H / 2 + 16
  const boxes = Array.from({ length: n }, (_, i) => {
    const a = -Math.PI / 2 + ((rtl ? -1 : 1) * 2 * Math.PI * i) / n
    const w = 150
    return { x: cx + r * Math.cos(a) * 1.35 - w / 2, y: cy + r * Math.sin(a) - NODE_H / 2, w, h: NODE_H }
  })
  return { boxes, height: 2 * r + NODE_H + 32, width: W }
}

/** Nodes per row from the rendered width, so labels stay readable on a phone. */
function usePerRow(): [React.RefObject<HTMLDivElement | null>, number] {
  const ref = useRef<HTMLDivElement>(null)
  const [perRow, setPerRow] = useState(3)
  useEffect(() => {
    const el = ref.current
    if (!el || typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(([entry]) => {
      const w = entry.contentRect.width
      setPerRow(w < 440 ? 1 : w < 640 ? 2 : 3)
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  return [ref, perRow]
}

/** Point where the segment from a's centre towards b's centre leaves box a. */
function exitPoint(a: Box, b: Box): [number, number] {
  const ax = a.x + a.w / 2
  const ay = a.y + a.h / 2
  const dx = b.x + b.w / 2 - ax
  const dy = b.y + b.h / 2 - ay
  if (dx === 0 && dy === 0) return [ax, ay]
  const sx = dx !== 0 ? a.w / 2 / Math.abs(dx) : Infinity
  const sy = dy !== 0 ? a.h / 2 / Math.abs(dy) : Infinity
  const s = Math.min(sx, sy)
  return [ax + dx * s, ay + dy * s]
}

export function DiagramView({ props, verification }: { props: DiagramProps; verification?: Verification }) {
  const { t } = useI18n()
  const markerId = useId().replace(/:/g, '')
  const rtl = props.lang === 'ar'
  const [wrapRef, perRow] = usePerRow()
  const { boxes, height, width: W } =
    props.layout === 'cycle' ? cycleLayout(props.nodes.length, rtl) : flowLayout(props.nodes.length, rtl, perRow)
  const index = new Map(props.nodes.map((n, i) => [n.id, i]))
  const labelOf = (id: string) => stripUrls(props.nodes[index.get(id) ?? 0]?.label ?? id)

  return (
    <Card lang={props.lang} type="diagram" title={props.title} verification={verification}>
      <div ref={wrapRef} className="w-full">
      <svg
        viewBox={`0 0 ${W} ${height}`}
        style={{ maxWidth: W }}
        role="img"
        aria-label={t('diagram.label', { title: props.title })}
        data-testid="diagram"
        className="mx-auto block h-auto w-full"
      >
        <defs>
          <marker id={markerId} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M0,0 L10,5 L0,10 z" fill="var(--color-muted)" />
          </marker>
        </defs>
        {props.edges.map((e, i) => {
          const a = boxes[index.get(e.from) ?? 0]
          const b = boxes[index.get(e.to) ?? 0]
          const [x1, y1] = exitPoint(a, b)
          const [x2, y2] = exitPoint(b, a)
          return (
            <line key={i} data-testid="diagram-edge" x1={x1} y1={y1} x2={x2} y2={y2} stroke="var(--color-muted)" strokeWidth={1.6} markerEnd={`url(#${markerId})`} />
          )
        })}
        {props.nodes.map((n, i) => {
          const b = boxes[i]
          const lines = wrap(stripUrls(n.label))
          const lineH = 17
          const top = b.y + b.h / 2 - ((lines.length - 1) * lineH) / 2 + 5
          return (
            <g key={n.id} data-testid="diagram-node">
              <rect x={b.x} y={b.y} width={b.w} height={b.h} rx={12} fill={i === props.nodes.length - 1 ? 'var(--color-accent-soft)' : 'var(--color-raised)'} stroke={i === props.nodes.length - 1 ? 'var(--color-accent)' : 'var(--color-line)'} strokeWidth={1.5} />
              <text textAnchor="middle" fontSize={13.5} fontFamily={FONT} fill="var(--color-ink)" direction={rtl ? 'rtl' : 'ltr'}>
                {lines.map((l, j) => (
                  <tspan key={j} x={b.x + b.w / 2} y={top + j * lineH}>
                    {l}
                  </tspan>
                ))}
              </text>
            </g>
          )
        })}
        {/* Edge labels last, so nodes never cover them; above the line when the edge is horizontal. */}
        {props.edges.map((e, i) => {
          if (!e.label) return null
          const a = boxes[index.get(e.from) ?? 0]
          const b = boxes[index.get(e.to) ?? 0]
          const [x1, y1] = exitPoint(a, b)
          const [x2, y2] = exitPoint(b, a)
          const horizontal = Math.abs(y1 - y2) < 1
          const mx = (x1 + x2) / 2
          const my = horizontal ? y1 - 16 : (y1 + y2) / 2
          const label = stripUrls(e.label)
          const w = label.length * 7.2 + 12
          return (
            <g key={`l${i}`}>
              <rect x={mx - w / 2} y={my - 11} width={w} height={20} rx={6} fill="var(--color-surface)" stroke="var(--color-line)" />
              <text x={mx} y={my + 4} textAnchor="middle" fontSize={12} fontFamily={FONT} fill="var(--color-muted)" direction={rtl ? 'rtl' : 'ltr'}>
                {label}
              </text>
            </g>
          )
        })}
      </svg>
      </div>
      <ol className="sr-only">
        {props.edges.map((e, i) => (
          <li key={i}>
            {labelOf(e.from)} → {labelOf(e.to)}
            {e.label ? ` (${e.label})` : ''}
          </li>
        ))}
      </ol>
      {props.page ? (
        <p className="mb-0 mt-2 text-xs text-muted">
          <CitationChip page={props.page} />
        </p>
      ) : null}
    </Card>
  )
}
