import { useState } from 'react'
import { approveAction, rejectAction, type ActionEdits } from '../api/client'
import { HttpError } from '../api/sse'
import type { ActionCardProps, DecisionCardsProps, ProposedActionT, TaskCardsProps } from '../catalog/schemas'
import { useI18n } from '../i18n/context'
import { stripUrls } from '../lib/text'
import type { Verification } from '../state/useAnswer'
import { Card } from './Card'
import { CitationChip } from './CitationChip'
import { TypeIcon } from './TypeIcon'

function Avatar({ name }: { name: string }) {
  return (
    <span
      aria-hidden
      className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent-soft text-[11px] font-bold text-accent-strong"
    >
      {Array.from(name.trim())[0] ?? '?'}
    </span>
  )
}

/** Action items found in the document: who does what by when, each with its source sentence. */
export function TaskCards({ props, verification }: { props: TaskCardsProps; verification?: Verification }) {
  const { t } = useI18n()
  return (
    <Card lang={props.lang} type="task_cards" title={props.title} verification={verification}>
      <ul className="m-0 grid list-none grid-cols-[minmax(0,1fr)] gap-2 p-0 sm:grid-cols-2">
        {props.tasks.map((task, i) => (
          <li key={i} data-testid="task-item" className="grid content-start gap-2 rounded-xl bg-raised p-3">
            <p dir="auto" className="m-0 text-sm font-semibold leading-6 text-ink">
              {stripUrls(task.title)}
            </p>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
              <span data-testid="task-owner" className="flex items-center gap-1.5 font-semibold text-ink">
                <Avatar name={task.owner} />
                <bdi>{task.owner}</bdi>
              </span>
              {task.due_date ? (
                <span data-testid="task-due">
                  {t('action.due')}: <bdi>{task.due_date}</bdi>
                </span>
              ) : null}
              <CitationChip citation={task.citation} />
            </div>
          </li>
        ))}
      </ul>
    </Card>
  )
}

export function DecisionCards({ props, verification }: { props: DecisionCardsProps; verification?: Verification }) {
  const { num } = useI18n()
  return (
    <Card lang={props.lang} type="decision_cards" title={props.title} verification={verification}>
      <ol className="m-0 grid list-none gap-2 p-0">
        {props.decisions.map((d, i) => (
          <li key={i} data-testid="decision-item" className="flex items-start gap-3 rounded-xl bg-raised px-3 py-2.5">
            <span
              className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white"
              style={{ background: 'var(--color-band-decision_cards)' }}
            >
              {num(i + 1)}
            </span>
            <p dir="auto" className="m-0 min-w-0 text-sm leading-6 text-ink">
              {stripUrls(d.text)} <CitationChip citation={d.citation} />
            </p>
          </li>
        ))}
      </ol>
    </Card>
  )
}

type Status = 'proposed' | 'busy' | 'approved' | 'rejected' | 'error'
// Decisions survive the card unmounting (switching to the Tasks tab and back, or to another document).
const decisions = new Map<string, 'approved' | 'rejected'>()

function Field({ label, value, onChange, multiline = false, testid }: {
  label: string
  value: string
  onChange: (v: string) => void
  multiline?: boolean
  testid: string
}) {
  const cls = 'w-full rounded-lg border border-line bg-surface px-2.5 py-1.5 text-sm text-ink outline-none focus:border-accent'
  return (
    <label className="grid gap-1 text-xs font-semibold text-muted">
      {label}
      {multiline ? (
        <textarea dir="auto" rows={5} value={value} data-testid={testid} onChange={(e) => onChange(e.target.value)} className={cls} />
      ) : (
        <input dir="auto" value={value} data-testid={testid} onChange={(e) => onChange(e.target.value)} className={cls} />
      )}
    </label>
  )
}

/** One proposal with the permission gate: nothing happens until Approve. */
function ActionItem({ action }: { action: ProposedActionT }) {
  const { t } = useI18n()
  const [status, setStatus] = useState<Status>(() => decisions.get(action.proposal_id) ?? 'proposed')
  const [error, setError] = useState('')
  const [editing, setEditing] = useState(false)
  const isTask = action.kind === 'create_task'
  const [fields, setFields] = useState({
    title: action.title,
    owner: action.owner ?? '',
    due_date: action.due_date ?? '',
    to: action.to ?? '',
    body: action.body ?? '',
  })
  const flags = action.flags ?? []
  const hidden = flags.includes('FROM_HIDDEN_TEXT')

  const decide = async (approve: boolean) => {
    setStatus('busy')
    setError('')
    try {
      if (approve) {
        const edits: ActionEdits = {}
        if (editing) {
          for (const k of (isTask ? ['title', 'owner', 'due_date'] : ['title', 'to', 'body']) as (keyof typeof fields)[]) {
            const v = fields[k].trim()
            if (v && v !== (action[k] ?? '')) edits[k] = v
          }
        }
        await approveAction(action.proposal_id, edits)
        decisions.set(action.proposal_id, 'approved')
        setStatus('approved')
      } else {
        await rejectAction(action.proposal_id)
        decisions.set(action.proposal_id, 'rejected')
        setStatus('rejected')
      }
      setEditing(false)
    } catch (e) {
      setStatus('error')
      setError(e instanceof HttpError ? e.message : String(e))
    }
  }
  const shown = editing ? fields : { ...fields, title: action.title }
  const decided = status === 'approved' || status === 'rejected'

  return (
    <li
      data-testid="action-item"
      data-kind={action.kind}
      data-status={status}
      data-flags={flags.join(' ')}
      className={`grid gap-3 rounded-xl border p-3 ${hidden ? 'border-bad bg-bad-soft/40' : 'border-line bg-surface'}`}
    >
      <div className="flex flex-wrap items-center gap-2 text-xs font-semibold text-muted">
        <span className="flex items-center gap-1.5 rounded-full bg-raised px-2 py-0.5 text-ink">
          <TypeIcon type={isTask ? 'task_cards' : 'text'} className="h-3.5 w-3.5" />
          {t(isTask ? 'action.task' : 'action.draft')}
        </span>
        {action.citation ? <CitationChip citation={action.citation} /> : null}
      </div>
      {flags.length ? (
        <ul className="m-0 grid list-none gap-1 p-0">
          {flags.map((f) => (
            <li
              key={f}
              data-testid="action-flag"
              data-flag={f}
              role="alert"
              className={`rounded-lg px-2.5 py-1.5 text-xs font-semibold ${f === 'FROM_HIDDEN_TEXT' ? 'bg-bad-soft text-bad' : 'bg-warn-soft text-warn'}`}
            >
              <span aria-hidden className="me-1">⚠</span>
              {t(`flag.${f}`)}
            </li>
          ))}
        </ul>
      ) : null}

      {editing ? (
        <div className="grid gap-2">
          <Field label={t(isTask ? 'action.title' : 'action.subject')} value={fields.title} testid="edit-title" onChange={(v) => setFields({ ...fields, title: v })} />
          {isTask ? (
            <div className="grid gap-2 sm:grid-cols-2">
              <Field label={t('action.owner')} value={fields.owner} testid="edit-owner" onChange={(v) => setFields({ ...fields, owner: v })} />
              <Field label={t('action.due')} value={fields.due_date} testid="edit-due" onChange={(v) => setFields({ ...fields, due_date: v })} />
            </div>
          ) : (
            <>
              <Field label={t('action.to')} value={fields.to} testid="edit-to" onChange={(v) => setFields({ ...fields, to: v })} />
              <Field label={t('action.body')} value={fields.body} testid="edit-body" multiline onChange={(v) => setFields({ ...fields, body: v })} />
            </>
          )}
        </div>
      ) : (
        <div className="grid gap-1">
          <p dir="auto" data-testid="action-title" className="m-0 text-[15px] font-semibold leading-6 text-ink">
            {shown.title}
          </p>
          {isTask ? (
            <p className="m-0 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
              {action.owner ? (
                <span className="flex items-center gap-1.5 font-semibold text-ink">
                  <Avatar name={action.owner} />
                  <bdi>{action.owner}</bdi>
                </span>
              ) : null}
              {action.due_date ? (
                <span>
                  {t('action.due')}: <bdi>{action.due_date}</bdi>
                </span>
              ) : null}
            </p>
          ) : (
            <>
              {action.to ? (
                <p className="m-0 text-xs text-muted">
                  {t('action.to')}: <bdi className="font-semibold text-ink">{action.to}</bdi>
                </p>
              ) : null}
              {action.body ? (
                <p dir="auto" data-testid="action-body" className="m-0 whitespace-pre-line rounded-lg bg-raised p-2.5 text-sm leading-6 text-ink">
                  {stripUrls(action.body)}
                </p>
              ) : null}
            </>
          )}
        </div>
      )}

      {decided ? (
        <p
          data-testid="action-status"
          role="status"
          className={`m-0 rounded-lg px-2.5 py-1.5 text-xs font-semibold ${status === 'approved' ? 'bg-ok-soft text-ok' : 'bg-raised text-muted'}`}
        >
          {status === 'approved' ? (isTask ? `✓ ${t('action.approvedTask')}` : `✓ ${t('action.approvedDraft')}`) : t('action.rejected')}
        </p>
      ) : (
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            data-testid="action-approve"
            disabled={status === 'busy'}
            onClick={() => void decide(true)}
            className="rounded-full bg-accent px-4 py-1.5 text-sm font-semibold text-on-accent disabled:opacity-50"
          >
            {editing ? t('action.save') : t('action.approve')}
          </button>
          <button
            type="button"
            data-testid="action-edit"
            disabled={status === 'busy'}
            aria-pressed={editing}
            onClick={() => setEditing((e) => !e)}
            className="rounded-full border border-line px-4 py-1.5 text-sm font-semibold text-ink hover:bg-raised disabled:opacity-50"
          >
            {editing ? t('action.cancel') : t('action.edit')}
          </button>
          <button
            type="button"
            data-testid="action-reject"
            disabled={status === 'busy'}
            onClick={() => void decide(false)}
            className="rounded-full px-4 py-1.5 text-sm font-semibold text-bad hover:bg-bad-soft disabled:opacity-50"
          >
            {t('action.reject')}
          </button>
          {status === 'error' ? (
            <span role="alert" className="text-xs text-bad">
              <bdi>{error}</bdi>
            </span>
          ) : null}
        </div>
      )}
    </li>
  )
}

export function ActionCard({ props, verification }: { props: ActionCardProps; verification?: Verification }) {
  const { t } = useI18n()
  return (
    <Card lang={props.lang} type="action_card" title={props.title} verification={verification}>
      <p className="m-0 text-xs text-muted">{t('action.gate')}</p>
      <ul className="m-0 grid list-none gap-3 p-0">
        {props.actions.map((a) => (
          <ActionItem key={a.proposal_id} action={a} />
        ))}
      </ul>
    </Card>
  )
}
