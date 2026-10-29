import { answer, askText, componentTypes, expect, open, routeAsk, test, upload, waitDone } from '../helpers/fixtures'

test.describe('fallback', () => {
  test.beforeEach(async ({ page }) => {
    await open(page)
    await upload(page)
  })

  test('truncated output keeps the text and finished components, with a note', async ({ page }) => {
    await askText(page, 'truncated', { fixture: 'malformed/truncated' })
    await expect(answer(page)).toHaveAttribute('data-phase', 'done')
    await expect(page.getByTestId('answer-text')).toContainText('Chain-of-thought prompting')
    expect(await componentTypes(page)).toEqual(['comparison'])
    await expect(page.getByTestId('dropped-note')).toHaveCount(1)
    await expect(page.getByTestId('run-error')).toHaveCount(0)
  })

  test('an unknown component type is ignored', async ({ page }) => {
    await askText(page, 'unknown', { fixture: 'malformed/unknown_type' })
    expect(await componentTypes(page)).toEqual(['comparison'])
    await expect(page.getByTestId('dropped-note')).toHaveCount(0)
  })

  test('a RUN_ERROR shows a friendly retry message', async ({ page }) => {
    await askText(page, 'boom', { fixture: 'error/run_error' })
    const err = page.getByTestId('run-error')
    await expect(err).toBeVisible()
    await expect(err.getByRole('button')).toBeVisible()
    // Retrying (without the forced error) recovers.
    await routeAsk(page)
    await err.getByRole('button').click()
    await waitDone(page)
    await expect(page.getByTestId('run-error')).toHaveCount(0)
  })

  test('a backend 429 shows the rate-limit message', async ({ page, lang }) => {
    await page.route('**/api/ask', (route) =>
      route.fulfill({
        status: 429,
        contentType: 'application/json',
        body: JSON.stringify({ code: 'RATE_LIMITED', message: 'Too many requests.' }),
      }),
    )
    await page.getByTestId('suggest-q1').click()
    const err = page.getByTestId('run-error')
    await expect(err).toHaveAttribute('data-code', 'RATE_LIMITED')
    await expect(err).toContainText(lang === 'ar' ? 'طلبات كتير' : 'Too many requests')
  })
})
