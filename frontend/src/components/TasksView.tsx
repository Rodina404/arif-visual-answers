import { useEffect, useState } from 'react'
import { deleteTask, listTasks, type SavedItem } from '../api/client'
import { useI18n } from '../i18n/context'
import { isMostlyLatin } from '../lib/text'
import { Icon } from './Icons'

function Source({ item }: { item: SavedItem }) {
  const { t, num } = useI18n()
  if (!item.citation) return <span className="text-[11px] text-muted">{t('tasks.noSource')}</span>
  const q = item.citation.quote
  return (
    <span data-testid="task-source" className="grid gap-0.5 text-[11px] text-muted">
      <span className="flex items-center gap-1">
        <Icon name="file" className="h-3 w-3" />
        <bdi>{item.filename}</bdi> · {t('cite.page', { n: num(item.citation.page) })}
      </span>
      <q dir={isMostlyLatin(q) ? 'ltr' : 'rtl'} className={`line-clamp-2 text-ink/80 ${isMostlyLatin(q) ? 'ltr-island' : ''}`}>
        {q}
      </q>
    </span>
  )
}

/** Approved tasks (and saved drafts, never sent) for this browser, with delete. */
export function TasksView() {
  const { t } = useI18n()
  const [data, setData] = useState<{ tasks: SavedItem[]; drafts: SavedItem[] } | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    let live = true
    listTasks()
      .then((d) => live && setData(d))
      .catch(() => live && setError(true))
    return () => {
      live = false
    }
  }, [])

  const remove = async (id: string) => {
    await deleteTask(id).catch(() => undefined)
    setData((d) => (d ? { tasks: d.tasks.filter((x) => x.id !== id), drafts: d.drafts.filter((x) => x.id !== id) } : d))
  }

  if (error) return <p className="m-0 text-sm text-bad">{t('error.network')}</p>
  if (!data) return <p className="m-0 text-sm text-muted">{t('source.loading')}</p>
  return (
    <section data-testid="tasks-view" aria-labelledby="tasks-title" className="grid min-w-0 gap-5">
      <div className="grid gap-1">
        <h2 id="tasks-title" className="m-0 text-xl font-semibold text-ink">
          {t('tasks.title')}
        </h2>
        <p className="m-0 text-xs text-muted">{t('tasks.subtitle')}</p>
      </div>
      {data.tasks.length === 0 ? (
        <p data-testid="tasks-empty" className="m-0 rounded-2xl border border-dashed border-line px-4 py-8 text-center text-sm text-muted">
          {t('tasks.empty')}
        </p>
      ) : (
        <ul className="m-0 grid list-none gap-2 p-0">
          {data.tasks.map((task) => (
            <li key={task.id} data-testid="task-row" className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-3 rounded-2xl border border-line bg-surface p-3.5">
              <div className="grid min-w-0 gap-1.5">
                <p dir="auto" data-testid="task-title" className="m-0 text-[15px] font-semibold leading-6 text-ink">
                  {task.title}
                </p>
                <p className="m-0 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
                  <span>
                    {t('action.owner')}: <bdi data-testid="task-owner" className="font-semibold text-ink">{task.owner}</bdi>
                  </span>
                  {task.due_date ? (
                    <span>
                      {t('action.due')}: <bdi data-testid="task-due" className="font-semibold text-ink">{task.due_date}</bdi>
                    </span>
                  ) : null}
                  {task.edited ? <span className="rounded bg-raised px-1.5">{t('tasks.edited')}</span> : null}
                  {task.flags.length ? <span className="rounded bg-warn-soft px-1.5 text-warn">{t('tasks.flagged')}</span> : null}
                </p>
                <Source item={task} />
              </div>
              <button
                type="button"
                data-testid="task-delete"
                aria-label={t('tasks.delete', { name: task.title })}
                onClick={() => void remove(task.id)}
                className="flex h-8 w-8 items-center justify-center rounded-full text-muted hover:bg-bad-soft hover:text-bad"
              >
                <Icon name="close" className="h-4 w-4" />
              </button>
            </li>
          ))}
        </ul>
      )}
      {data.drafts.length ? (
        <div className="grid gap-2">
          <h3 className="m-0 text-sm font-semibold text-ink">{t('tasks.drafts')}</h3>
          <ul className="m-0 grid list-none gap-2 p-0">
            {data.drafts.map((d) => (
              <li key={d.id} data-testid="draft-row" className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-3 rounded-2xl border border-line bg-surface p-3.5">
                <div className="grid min-w-0 gap-1">
                  <p dir="auto" className="m-0 text-sm font-semibold text-ink">
                    {d.title}
                  </p>
                  <p className="m-0 text-xs text-muted">
                    {t('action.to')}: <bdi className="text-ink">{d.to}</bdi> · <span className="font-semibold">{t('tasks.notSent')}</span>
                  </p>
                  <p dir="auto" className="m-0 line-clamp-3 whitespace-pre-line text-xs text-muted">
                    {d.body}
                  </p>
                </div>
                <button
                  type="button"
                  data-testid="task-delete"
                  aria-label={t('tasks.delete', { name: d.title })}
                  onClick={() => void remove(d.id)}
                  className="flex h-8 w-8 items-center justify-center rounded-full text-muted hover:bg-bad-soft hover:text-bad"
                >
                  <Icon name="close" className="h-4 w-4" />
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  )
}
