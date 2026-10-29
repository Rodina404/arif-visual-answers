import AxeBuilder from '@axe-core/playwright'
import { askDemo, expect, open, test, upload } from '../helpers/fixtures'

for (const qid of ['q1', 'q2', 'q3', 'q5', 'q6']) {
  test(`axe: no WCAG A/AA violations after ${qid} renders`, async ({ page }) => {
    await open(page)
    await upload(page)
    await askDemo(page, qid)
    if (qid === 'q1') await page.getByTestId('quiz-question').first().getByRole('radio').first().check()
    if (qid === 'q5') await page.getByTestId('flashcard').first().click()
    const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze()
    const summary = results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).slice(0, 3).join(' | ')}`)
    expect(summary).toEqual([])
  })
}

test('chart has role=img, a label and a hidden data table; quiz uses fieldset + radios', async ({ page }) => {
  await open(page)
  await upload(page)
  await askDemo(page, 'q2')
  const chart = page.getByTestId('chart')
  await expect(chart).toHaveAttribute('role', 'img')
  await expect(chart).toHaveAttribute('aria-label', /540B/)
  await expect(page.locator('[data-component="chart"] .sr-only table')).toHaveCount(1)
  await askDemo(page, 'q1')
  await expect(page.locator('fieldset[data-testid="quiz-question"] legend')).toHaveCount(2)
  await expect(page.locator('fieldset input[type="radio"]')).toHaveCount(8)
})
