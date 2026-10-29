import { askDemo, expect, open, openMenu, test, upload } from '../helpers/fixtures'

async function centerX(loc: import('@playwright/test').Locator) {
  const b = await loc.boundingBox()
  if (!b) throw new Error('no bounding box')
  return b.x + b.width / 2
}

test.describe('direction', () => {
  test('html dir/lang and header start side', async ({ page, lang }) => {
    await open(page)
    const html = page.locator('html')
    await expect(html).toHaveAttribute('dir', lang === 'ar' ? 'rtl' : 'ltr')
    await expect(html).toHaveAttribute('lang', lang)
    await openMenu(page)
    const brand = await centerX(page.getByTestId('brand'))
    const toggle = await centerX(page.getByTestId('lang-toggle'))
    // The brand sits on the start side: right in RTL, left in LTR.
    expect(lang === 'ar' ? brand > toggle : brand < toggle).toBe(true)
  })

  test('chart and table mirror; quotes stay LTR islands', async ({ page, lang }) => {
    await open(page)
    await upload(page)
    await askDemo(page, 'q2')
    const ticks = page.getByTestId('chart').locator('.recharts-cartesian-axis-tick-value')
    await expect(ticks.filter({ hasText: /^8B$/ })).toHaveCount(1)
    const first = await centerX(ticks.filter({ hasText: /^8B$/ }))
    const last = await centerX(ticks.filter({ hasText: /^540B$/ }))
    expect(lang === 'ar' ? first > last : first < last).toBe(true)

    const chip = page.getByTestId('chart-point').first().getByTestId('citation-chip')
    await chip.hover()
    await expect(page.getByRole('tooltip').locator('q')).toHaveAttribute('dir', 'ltr')

    await askDemo(page, 'q3')
    const th = page.locator('[data-component="table"]').first().locator('th')
    const col1 = await centerX(th.nth(0))
    const col2 = await centerX(th.nth(1))
    expect(lang === 'ar' ? col1 > col2 : col1 < col2).toBe(true)
  })

  test('the toggle switches direction without a reload and persists', async ({ page, lang }) => {
    await open(page)
    const other = lang === 'ar' ? 'en' : 'ar'
    await page.evaluate(() => ((window as unknown as { marker: number }).marker = 42))
    await openMenu(page)
    await page.getByTestId('lang-toggle').locator(`button[lang="${other}"]`).click()
    await expect(page.locator('html')).toHaveAttribute('dir', other === 'ar' ? 'rtl' : 'ltr')
    expect(await page.evaluate(() => (window as unknown as { marker?: number }).marker)).toBe(42)
    await page.reload()
    await expect(page.locator('html')).toHaveAttribute('lang', other)
  })

  test('no horizontal scroll at 390 px @mobile', async ({ page }) => {
    await open(page)
    await upload(page)
    for (const q of ['q1', 'q2', 'q3', 'q6']) {
      await askDemo(page, q)
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
      expect(overflow, `horizontal overflow after ${q}`).toBeLessThanOrEqual(0)
    }
  })
})
