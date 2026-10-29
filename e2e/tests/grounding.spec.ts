import { answer, askDemo, askText, expect, open, test, upload } from '../helpers/fixtures'

test.describe('grounding', () => {
  test.beforeEach(async ({ page }) => {
    await open(page)
    await upload(page)
  })

  test('every chart point has a page chip', async ({ page }) => {
    await askDemo(page, 'q2')
    const points = page.getByTestId('chart-point')
    await expect(points).toHaveCount(6)
    for (const p of await points.all()) await expect(p.getByTestId('citation-chip')).toHaveAttribute('data-page', '21')
  })

  test('every table row has a page chip', async ({ page }) => {
    await askDemo(page, 'q3')
    const rows = page.getByTestId('table-row')
    await expect(rows).toHaveCount(8)
    for (const r of await rows.all()) await expect(r.getByTestId('citation-chip')).toHaveCount(1)
  })

  test('a chip opens the source panel with the quote highlighted', async ({ page }) => {
    await askDemo(page, 'q2')
    const chip = page.getByTestId('chart-point').last().getByTestId('citation-chip')
    await chip.hover()
    await expect(page.getByRole('tooltip')).toContainText('540B 17.9 56.9')
    await chip.click()
    const panel = page.getByTestId('source-panel')
    await expect(panel).toBeVisible()
    await expect(panel.getByTestId('source-highlight')).toContainText('540B 17.9 56.9')
    await page.keyboard.press('Escape')
    await expect(panel).toHaveCount(0)
  })

  test('a chart value missing from its quote is removed and flagged', async ({ page }) => {
    await askText(page, 'bad number test', { fixture: 'malformed/bad_number' })
    const chart = answer(page).locator('[data-component="chart"]')
    await expect(chart).toHaveAttribute('data-verification', 'partial')
    await expect(chart.getByTestId('partial-note')).toBeVisible()
    await expect(page.getByTestId('chart-point')).toHaveCount(6)
  })

  test('a chart left with two verified points renders as a table', async ({ page }) => {
    await askText(page, 'two point test', { fixture: 'malformed/two_point_chart' })
    await expect(answer(page).locator('[data-component="chart"]')).toHaveCount(0)
    const table = answer(page).locator('[data-component="table"]')
    await expect(table).toBeVisible()
    await expect(table.getByTestId('table-row')).toHaveCount(2)
    await expect(table.getByTestId('partial-note')).toBeVisible()
  })
})
