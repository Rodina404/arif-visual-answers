// Quick visual check: upload cot.pdf, ask a demo question, screenshot. Usage:
//   node ../e2e/helpers/shoot.mjs <lang> <qid> <width> <out.png> [compare]
import { chromium } from '@playwright/test'
import path from 'node:path'

const [lang = 'ar', qid = 'q1', width = '1280', out = 'shot.png', mode] = process.argv.slice(2)
const pdf = path.resolve(import.meta.dirname, '../../fixtures/pdfs/cot.pdf')
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: Number(width), height: 900 }, locale: lang === 'ar' ? 'ar-EG' : 'en-US' })
await page.addInitScript((l) => localStorage.setItem('arif.lang', l), lang)
await page.goto(mode === 'compare' ? 'http://localhost:8000/compare' : 'http://localhost:8000/')
await page.getByTestId('file-input').setInputFiles(pdf)
await page.getByTestId('doc-pages').waitFor()
await page.getByTestId(`suggest-${qid}`).click()
await page.locator('[data-testid="answer"][data-phase="done"]').last().waitFor({ timeout: 20000 })
await page.waitForTimeout(400)
const scrollW = await page.evaluate(() => document.documentElement.scrollWidth)
console.log(JSON.stringify({ lang, qid, width, scrollWidth: scrollW, dir: await page.evaluate(() => document.documentElement.dir) }))
await page.screenshot({ path: out, fullPage: true })
await browser.close()
