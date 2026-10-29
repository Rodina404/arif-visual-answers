// Capture a fixed set of screens for design reviews. Usage (server on :8000):
//   node helpers/gallery.mjs ../data/design/before
import { chromium } from '@playwright/test'
import fs from 'node:fs'
import path from 'node:path'

const out = path.resolve(process.argv[2] ?? '../data/design/shots')
fs.mkdirSync(out, { recursive: true })
const pdf = path.resolve(import.meta.dirname, '../../fixtures/pdfs/cot.pdf')
const BASE = process.env.BASE ?? 'http://localhost:8000'

const SCREENS = [
  { name: '01-ar-home', lang: 'ar', width: 1280 },
  { name: '02-ar-ask-q1', lang: 'ar', width: 1280, q: 'q1' },
  { name: '03-en-ask-q2', lang: 'en', width: 1280, q: 'q2' },
  { name: '04-ar-ask-q3', lang: 'ar', width: 1280, q: 'q3' },
  { name: '05-en-ask-q5', lang: 'en', width: 1280, q: 'q5', flip: true },
  { name: '06-ar-ask-q6', lang: 'ar', width: 1280, q: 'q6' },
  { name: '07-ar-quiz-correct', lang: 'ar', width: 1280, q: 'q1', quiz: true },
  { name: '08-ar-compare-q1', lang: 'ar', width: 1280, q: 'q1', compare: true },
  { name: '09-en-compare-q2', lang: 'en', width: 1280, q: 'q2', compare: true },
  { name: '10-ar-home-390', lang: 'ar', width: 390 },
  { name: '11-ar-ask-q2-390', lang: 'ar', width: 390, q: 'q2' },
  { name: '12-en-ask-q1-390', lang: 'en', width: 390, q: 'q1' },
  { name: '13-ar-compare-q1-390', lang: 'ar', width: 390, q: 'q1', compare: true },
  { name: '14-ar-ask-q4', lang: 'ar', width: 1280, q: 'q4' },
]

const browser = await chromium.launch()
for (const s of SCREENS) {
  const page = await browser.newPage({ viewport: { width: s.width, height: s.width < 500 ? 844 : 900 }, reducedMotion: 'reduce' })
  await page.addInitScript((l) => localStorage.setItem('arif.lang', l), s.lang)
  await page.goto(s.compare ? `${BASE}/compare` : `${BASE}/`)
  await page.getByTestId('app-header').waitFor()
  if (s.q) {
    await page.getByTestId('file-input').setInputFiles(pdf)
    await page.getByTestId('doc-pages').waitFor()
    await page.getByTestId(`suggest-${s.q}`).click()
    await page.locator('[data-testid="answer"][data-phase="done"]').last().waitFor({ timeout: 30000 })
    if (s.compare) await page.getByTestId('compare-diff').waitFor({ timeout: 30000 })
    if (s.flip) await page.getByTestId('flashcard').first().click()
    if (s.quiz) {
      const q = page.getByTestId('quiz-question').first()
      await q.scrollIntoViewIfNeeded()
      await q.getByRole('radio').nth(1).check()
      await page.waitForTimeout(150)
      await page.getByTestId('component').filter({ has: q }).screenshot({ path: path.join(out, `${s.name}.png`) })
      await page.close()
      continue
    }
  }
  await page.waitForTimeout(300)
  await page.screenshot({ path: path.join(out, `${s.name}.png`), fullPage: true })
  await page.close()
}
await browser.close()
console.log('saved', SCREENS.length, 'screens to', out)
