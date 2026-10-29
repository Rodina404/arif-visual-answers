import fs from 'node:fs'
import path from 'node:path'
import { answer, expect, open, openMenu, PDFS, ROOT, routeAsk, test, upload, waitDone } from '../helpers/fixtures'

const OUT = path.join(ROOT, 'demo')
const SHOTS = path.join(OUT, 'shots')

/** The build spec (docs/BUILD_SPEC.md §16) demo script, recorded as video plus key frames. Run with `make demo`. */
test('demo recording @demo', async ({ page }) => {
  fs.mkdirSync(SHOTS, { recursive: true })
  const shot = (name: string) => page.screenshot({ path: path.join(SHOTS, `${name}.png`) })
  const pause = (ms = 1200) => page.waitForTimeout(ms)
  await routeAsk(page) // fresh (uncached) answers so the streaming is visible

  // 0:00 Problem: the Before/After tab with the CoT paper uploaded.
  await open(page, 'compare')
  await upload(page, PDFS.cot)
  await pause()

  // 0:20 Same model, same question: long prose vs short answer + visuals.
  await page.getByTestId('suggest-q1').click()
  await expect(page.getByTestId('skeleton').first()).toBeVisible()
  await shot('01-ar-streaming')
  await expect(page.getByTestId('compare-diff')).toBeVisible({ timeout: 30_000 })
  await shot('02-ar-before-after')
  await page.getByTestId('panel-after').getByTestId('quiz-question').first().scrollIntoViewIfNeeded()
  await pause()

  // Answer one quiz question.
  const quiz = page.getByTestId('panel-after').getByTestId('quiz-question').first()
  await quiz.getByRole('radio').nth(1).check()
  await pause()
  await shot('03-ar-quiz')

  // 1:00 Trust: open a page chip.
  const chip = page.getByTestId('panel-after').locator('[data-component="comparison"]').getByTestId('citation-chip').last()
  await chip.scrollIntoViewIfNeeded()
  await chip.hover()
  await pause(800)
  await chip.click()
  await expect(page.getByTestId('source-highlight')).toBeVisible()
  await pause(1500)
  await shot('04-ar-source-panel')
  await page.keyboard.press('Escape')

  // 1:30 Restraint: q4 is plain text.
  await openMenu(page)
  await page.getByTestId('tab-ask').click()
  await page.getByTestId('suggest-q4').click()
  await waitDone(page)
  await pause()
  await shot('05-ar-text-only')

  // 1:45 Toggle to English, ask q2: the chart mirrors back to LTR.
  await openMenu(page)
  await page.getByTestId('lang-toggle').locator('button[lang="en"]').click()
  await page.keyboard.press('Escape')
  await page.getByTestId('suggest-q2').click()
  await waitDone(page)
  await page.getByTestId('chart').scrollIntoViewIfNeeded()
  await pause()
  await shot('06-en-chart')

  // 2:05 Cost and latency: the metrics drawer.
  const drawer = answer(page).getByTestId('metrics-drawer')
  await drawer.scrollIntoViewIfNeeded()
  await drawer.locator('summary').click()
  await pause(1500)
  await shot('07-en-metrics')

  // 2:30 Security: the injection PDF.
  await page.evaluate(() => window.scrollTo(0, 0))
  await upload(page, PDFS.injection)
  await expect(page.locator('[data-testid="warning"][data-code="HIDDEN_TEXT_DETECTED"]').first()).toBeVisible()
  await pause(1500)
  await shot('08-en-injection-warning')

  const video = page.video()
  await page.close()
  if (video) await video.saveAs(path.join(OUT, 'arif-visual-answers.webm'))
})
