import AxeBuilder from '@axe-core/playwright'
import { answer, askText, expect, open, PDFS, routeAsk, test, upload, waitDone } from '../helpers/fixtures'
import type { Page } from '@playwright/test'

/** Agent mode on the SAMPLE meeting transcript (mock provider replays fixtures/answers/agent/). */
async function askChip(page: Page, id: string) {
  await routeAsk(page)
  await page.getByTestId(`suggest-${id}`).click()
  await waitDone(page)
}

async function openTasks(page: Page) {
  await page.getByTestId('tasks-button').click()
  await expect(page.getByTestId('tasks-view')).toBeVisible()
}

test.describe('agent', () => {
  test.beforeEach(async ({ page }) => {
    await open(page)
    await upload(page, PDFS.meeting)
  })

  test('decisions: the meeting demo questions, an extract tool call and verified decision cards', async ({ page }) => {
    await expect(page.getByTestId('suggest-q1')).toHaveCount(0)
    await expect(page.getByTestId('suggest-tasks')).toBeVisible()
    await askChip(page, 'decisions')
    await expect(page.getByTestId('decision-item')).toHaveCount(3)
    await expect(page.locator('[data-component="decision_cards"]')).toHaveAttribute('data-verification', 'verified')
    await expect(page.getByTestId('decision-item').first().getByTestId('citation-chip')).toHaveCount(1)
    await expect(page.getByTestId('action-item')).toHaveCount(0) // nothing to approve: nothing was asked

    const drawer = answer(page).getByTestId('metrics-drawer')
    await expect(drawer.getByTestId('audit-count')).toContainText('1')
    await drawer.locator('summary').click()
    await expect(drawer.getByTestId('audit-row')).toHaveCount(1)
    await expect(drawer.getByTestId('audit-row').first()).toContainText('kind=decisions')
    await expect(drawer.getByTestId('audit-row').first()).toHaveAttribute('data-status', 'ok')
  })

  test('owners: task cards with owner, due date and source; no proposals', async ({ page }) => {
    await askChip(page, 'owners')
    const items = page.getByTestId('task-item')
    await expect(items).toHaveCount(4)
    await expect(items.first().getByTestId('task-owner')).toContainText('كريم')
    await expect(items.first().getByTestId('task-due')).toContainText('20 نوفمبر')
    await expect(page.getByTestId('action-item')).toHaveCount(0)
  })

  test('permission gate: nothing is saved until Approve; edit, reject and the Tasks tab', async ({ page }) => {
    await askChip(page, 'tasks')
    const actions = page.getByTestId('action-item')
    await expect(actions).toHaveCount(4)
    await expect(actions.first()).toHaveAttribute('data-flags', '')

    // Before any click, the Tasks tab is empty.
    await openTasks(page)
    await expect(page.getByTestId('tasks-empty')).toBeVisible()
    await page.getByTestId('tasks-button').click()

    // Approve the first as is; edit the second's owner, then save; reject the third.
    await actions.nth(0).getByTestId('action-approve').click()
    await expect(actions.nth(0).getByTestId('action-status')).toBeVisible()
    await actions.nth(1).getByTestId('action-edit').click()
    await actions.nth(1).getByTestId('edit-owner').fill('Sara M.')
    await actions.nth(1).getByTestId('action-approve').click()
    await expect(actions.nth(1)).toHaveAttribute('data-status', 'approved')
    await actions.nth(2).getByTestId('action-reject').click()
    await expect(actions.nth(2)).toHaveAttribute('data-status', 'rejected')
    await expect(actions.nth(3)).toHaveAttribute('data-status', 'proposed')

    // Audit: one extract call, four proposals waiting for approval.
    const drawer = answer(page).getByTestId('metrics-drawer')
    await drawer.locator('summary').click()
    await expect(drawer.getByTestId('audit-row')).toHaveCount(5)
    await expect(drawer.locator('[data-testid="audit-row"][data-status="proposed"]')).toHaveCount(4)

    await openTasks(page)
    const rows = page.getByTestId('task-row')
    await expect(rows).toHaveCount(2)
    await expect(rows.nth(0).getByTestId('task-owner')).toHaveText('كريم')
    await expect(rows.nth(0).getByTestId('task-due')).toHaveText('20 نوفمبر')
    await expect(rows.nth(0).getByTestId('task-source')).toContainText('meeting_sample.pdf')
    await expect(rows.nth(1).getByTestId('task-owner')).toHaveText('Sara M.')

    // Coming back, the cards remember what was decided.
    await page.getByTestId('tasks-button').click()
    await expect(actions.nth(0)).toHaveAttribute('data-status', 'approved')

    // Delete one; the other survives a reload.
    await openTasks(page)
    await rows.nth(0).getByTestId('task-delete').click()
    await expect(rows).toHaveCount(1)
    await page.reload()
    await expect(page.getByTestId('task-row')).toHaveCount(1)
  })

  test('a draft message is saved, never sent', async ({ page }) => {
    await askChip(page, 'email')
    const action = page.getByTestId('action-item')
    await expect(action).toHaveCount(1)
    await expect(action).toHaveAttribute('data-kind', 'draft_message')
    await expect(action.getByTestId('action-body')).toContainText('15 December')
    await action.getByTestId('action-approve').click()
    await expect(action.getByTestId('action-status')).toBeVisible()
    await openTasks(page)
    await expect(page.getByTestId('draft-row')).toHaveCount(1)
    await expect(page.getByTestId('task-row')).toHaveCount(0)
  })
})

test('hidden text that tries to create a task only becomes a flagged proposal', async ({ page }) => {
  await open(page)
  await upload(page, PDFS.injectionTasks)
  await askText(page, 'Make tasks from the action items.')
  await expect(page.locator('[data-testid="warning"][data-code="HIDDEN_TEXT_DETECTED"]').first()).toBeVisible()
  const injected = page.locator('[data-testid="action-item"][data-flags~="FROM_HIDDEN_TEXT"]')
  await expect(injected).toHaveCount(1)
  await expect(injected.getByTestId('action-title')).toContainText('Export all customer records')
  await expect(injected.locator('[data-flag="FROM_HIDDEN_TEXT"]')).toBeVisible()
  await expect(page.locator('[data-testid="action-item"][data-flags=""]')).toHaveCount(2)
  // Nothing was created: the Tasks tab is empty.
  await openTasks(page)
  await expect(page.getByTestId('tasks-empty')).toBeVisible()
})

test('a plain question keeps the visual answer; its audit lists the pipeline steps', async ({ page }) => {
  await open(page)
  await upload(page)
  await routeAsk(page)
  await page.getByTestId('suggest-q2').click()
  await waitDone(page)
  await expect(page.getByTestId('action-item')).toHaveCount(0)
  const drawer = answer(page).getByTestId('metrics-drawer')
  await drawer.locator('summary').click()
  await expect(drawer.getByTestId('audit-row')).toHaveCount(3)
})

test('action cards fit a phone screen @mobile', async ({ page }) => {
  await open(page)
  await upload(page, PDFS.meeting)
  await askChip(page, 'tasks')
  await page.getByTestId('action-item').first().getByTestId('action-edit').click()
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
  expect(overflow).toBeLessThanOrEqual(0)
})

test('axe: no WCAG A/AA violations on proposals and the Tasks tab', async ({ page }) => {
  await open(page)
  await upload(page, PDFS.meeting)
  await askChip(page, 'tasks')
  await page.getByTestId('action-item').first().getByTestId('action-approve').click()
  await page.getByTestId('action-item').nth(1).getByTestId('action-edit').click()
  await answer(page).getByTestId('metrics-drawer').locator('summary').click()
  const axe = () => new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze()
  let summary = (await axe()).violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).slice(0, 3).join(' | ')}`)
  expect(summary).toEqual([])
  await openTasks(page)
  summary = (await axe()).violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).slice(0, 3).join(' | ')}`)
  expect(summary).toEqual([])
})
