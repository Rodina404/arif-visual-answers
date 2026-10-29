import { answer, askText, expect, open, test, upload } from '../helpers/fixtures'

test('the same question twice is a cache hit the second time', async ({ page }) => {
  await open(page)
  await upload(page)
  // A unique suffix gives a fresh cache key; the mock still matches q4 by keyword ("authors").
  const q = `Who are the authors? (cache check ${Date.now()}-${Math.random().toString(36).slice(2)})`
  await askText(page, q, { cache: true })
  const json = () => answer(page).getByTestId('metrics-json').textContent()
  await answer(page).getByTestId('metrics-drawer').locator('summary').click()
  expect(JSON.parse((await json()) ?? '{}').cache.app_cache_hit).toBe(false)

  await askText(page, q, { cache: true })
  await expect(answer(page).getByTestId('metric-cached')).toBeVisible()
  await answer(page).getByTestId('metrics-drawer').locator('summary').click()
  const m = JSON.parse((await json()) ?? '{}')
  expect(m.cache.app_cache_hit).toBe(true)
  expect(m.latency_ms.total).toBeLessThan(300)
})
