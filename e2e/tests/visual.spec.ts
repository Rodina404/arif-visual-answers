import { answer, askDemo, askText, expect, open, openMenu, test, upload, waitDone, routeAsk } from '../helpers/fixtures'

const masks = (page: import('@playwright/test').Page) => [page.getByTestId('metric-time')]

const CASES: [string, string, string][] = [
  ['q1', 'comparison', 'comparison'],
  ['q1', 'steps', 'steps'],
  ['q1', 'quiz', 'quiz'],
  ['q2', 'chart', 'chart'],
  ['q2', 'text', 'text'],
  ['q3', 'table', 'table'],
  ['q5', 'flashcards', 'flashcards'],
  ['q6', 'diagram', 'diagram'],
]

test.describe('visual', () => {
  test.beforeEach(async ({ page }) => {
    await open(page)
    await upload(page)
  })

  for (const [qid, type, name] of CASES) {
    test(`component: ${name}`, async ({ page }) => {
      await askDemo(page, qid)
      const comp = page.locator(`[data-testid="component"][data-type="${type}"]`).first()
      await comp.scrollIntoViewIfNeeded()
      await expect(comp).toHaveScreenshot(`${name}.png`)
    })
  }

  test('component: formula', async ({ page }) => {
    await askText(page, 'formula', { fixture: 'test/formula' })
    const comp = page.locator('[data-testid="component"][data-type="formula"]')
    await expect(comp.locator('.katex')).toBeVisible()
    await expect(comp).toHaveScreenshot('formula.png')
  })

  test('before/after view (q1)', async ({ page }) => {
    await openMenu(page)
    await page.getByTestId('tab-compare').click()
    await routeAsk(page)
    await page.getByTestId('suggest-q1').click()
    await waitDone(page)
    await expect(page.getByTestId('compare-diff')).toBeVisible({ timeout: 20_000 })
    await expect(page.getByTestId('before-text')).toBeVisible()
    await expect(page.locator('main')).toHaveScreenshot('before-after.png', {
      mask: [...masks(page), page.getByTestId('compare-diff')],
      fullPage: true,
    })
    await expect(answer(page)).toBeVisible()
  })
})
