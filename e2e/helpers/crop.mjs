// Screenshot only the first component on the page (smaller image to inspect).
import { chromium } from '@playwright/test'
import path from 'node:path'
const [lang, qid, width, out, mode] = process.argv.slice(2)
const pdf = path.resolve(import.meta.dirname, '../../fixtures/pdfs/cot.pdf')
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: Number(width), height: 900 } })
await page.addInitScript((l) => localStorage.setItem('arif.lang', l), lang)
await page.goto(mode === 'compare' ? 'http://localhost:8000/compare' : 'http://localhost:8000/')
await page.getByTestId('file-input').setInputFiles(pdf)
await page.getByTestId('doc-pages').waitFor()
await page.getByTestId(`suggest-${qid}`).click()
await page.locator('[data-testid="answer"][data-phase="done"]').last().waitFor({ timeout: 20000 })
await page.waitForTimeout(300)
const target = mode === 'compare' ? page.locator('main') : page.getByTestId('component').first()
await target.screenshot({ path: out })
await browser.close()
