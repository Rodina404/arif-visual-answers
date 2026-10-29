import fs from 'node:fs'
import path from 'node:path'
import { answer, askDemo, expect, open, ROOT, test, upload } from '../helpers/fixtures'

const env = fs.existsSync(path.join(ROOT, '.env')) ? fs.readFileSync(path.join(ROOT, '.env'), 'utf-8') : ''
const hasKey = Boolean(process.env.GEMINI_API_KEY || /GEMINI_API_KEY=\S+/.test(env))

// One live Gemini call (q1, Arabic). Run with `make test-live` (LIVE=1 starts a non-mock server on :8001).
test('live smoke: q1 in Arabic against the real model @live', async ({ page }) => {
  test.skip(!hasKey || process.env.LIVE !== '1', 'needs GEMINI_API_KEY and LIVE=1')
  test.setTimeout(120_000)
  await open(page)
  await upload(page)
  await askDemo(page, 'q1', { cache: true })
  await expect(answer(page)).toHaveAttribute('data-phase', 'done')
  await expect(page.getByTestId('run-error')).toHaveCount(0)
  await expect(page.getByTestId('answer-text')).not.toBeEmpty()
  expect(await page.getByTestId('component').count()).toBeGreaterThanOrEqual(1)
  for (const p of await page.getByTestId('chart-point').all()) await expect(p.getByTestId('citation-chip')).toHaveCount(1)
  for (const r of await page.getByTestId('table-row').all()) await expect(r.getByTestId('citation-chip')).toHaveCount(1)
  await answer(page).getByTestId('metrics-drawer').locator('summary').click()
  const m = JSON.parse((await answer(page).getByTestId('metrics-json').textContent()) ?? '{}')
  expect(m.tokens.total).toBeGreaterThan(0)
  expect(m.cost_usd.total).toBeGreaterThan(0)
  fs.mkdirSync(path.join(ROOT, 'data'), { recursive: true })
  fs.writeFileSync(path.join(ROOT, 'data', 'live-metrics.json'), JSON.stringify(m, null, 2))
})
