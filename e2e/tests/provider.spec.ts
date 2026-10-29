import { answer, askDemo, expect, open, test, upload } from '../helpers/fixtures'

test.describe('provider switch', () => {
  test.beforeEach(async ({ page }) => {
    await open(page)
    await upload(page)
  })

  test('Gemini is the default; Groq answers are labelled and use retrieval', async ({ page }) => {
    const sw = page.getByTestId('provider-switch')
    await expect(sw.locator('button')).toHaveCount(2)
    await expect(sw.locator('[data-provider="gemini"]')).toHaveAttribute('aria-pressed', 'true')

    await askDemo(page, 'q4')
    await expect(answer(page).getByTestId('metric-provider')).toContainText('gemini')
    await answer(page).getByTestId('metrics-drawer').locator('summary').click()
    await expect(answer(page).getByTestId('metrics-retrieval')).toContainText(/Whole document|الملف كله/)

    await sw.locator('[data-provider="groq"]').click()
    await expect(sw.locator('[data-provider="groq"]')).toHaveAttribute('aria-pressed', 'true')
    await askDemo(page, 'q2')
    const strip = answer(page).getByTestId('metric-provider')
    await expect(strip).toContainText('groq')
    await expect(strip).toContainText('openai/gpt-oss-120b')
    await answer(page).getByTestId('metrics-drawer').locator('summary').click()
    await expect(answer(page).getByTestId('metrics-retrieval')).toContainText('21')
  })

  test('the provider choice survives a reload', async ({ page }) => {
    await page.getByTestId('provider-switch').locator('[data-provider="groq"]').click()
    await page.reload()
    await expect(page.getByTestId('provider-switch').locator('[data-provider="groq"]')).toHaveAttribute(
      'aria-pressed',
      'true',
    )
  })
})
