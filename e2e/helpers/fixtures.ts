import { test as base, expect, type Locator, type Page } from '@playwright/test'
import fs from 'node:fs'
import path from 'node:path'

export const ROOT = path.resolve(import.meta.dirname, '../..')
export const PDFS = {
  cot: path.join(ROOT, 'fixtures/pdfs/cot.pdf'),
  injection: path.join(ROOT, 'fixtures/pdfs/injection.pdf'),
  tiny: path.join(ROOT, 'fixtures/pdfs/tiny.pdf'),
  notpdf: path.join(ROOT, 'fixtures/pdfs/notpdf.pdf'),
  meeting: path.join(ROOT, 'fixtures/pdfs/meeting_sample.pdf'),
  injectionTasks: path.join(ROOT, 'fixtures/pdfs/injection_tasks.pdf'),
}
const INDEX = JSON.parse(fs.readFileSync(path.join(ROOT, 'fixtures/answers/index.json'), 'utf-8'))
export const QUESTIONS: Record<string, { en: string; ar: string }> = INDEX.questions.cot
export const INJECTION_Q: { en: string; ar: string } = INDEX.questions.injection.q1

export type Lang = 'ar' | 'en'

export const test = base.extend<{ lang: Lang }>({
  lang: async ({}, use, info) => use((info.project.metadata.lang as Lang) ?? 'ar'),
  page: async ({ page, lang }, use) => {
    // Only a default: a choice made in the test (toggle) survives reloads.
    await page.addInitScript((l) => {
      try {
        if (!localStorage.getItem('arif.lang')) localStorage.setItem('arif.lang', l)
      } catch {
        /* ignore */
      }
    }, lang)
    await use(page)
  },
})
export { expect }

export interface AskOpts {
  fixture?: string // forces fixtures/answers/<fixture>.json (mock mode only)
  cache?: boolean // default false: bypass the answer cache so streaming is visible
}

/** Add test headers to /api/ask* requests. */
export async function routeAsk(page: Page, opts: AskOpts = {}) {
  await page.unroute('**/api/ask*')
  await page.route('**/api/ask*', (route) => {
    const headers = { ...route.request().headers() }
    if (!opts.cache) headers['x-no-cache'] = '1'
    if (opts.fixture) headers['x-mock-fixture'] = opts.fixture
    return route.continue({ headers })
  })
}

export async function open(page: Page, view: 'ask' | 'compare' = 'ask') {
  await page.goto(view === 'compare' ? '/compare' : '/')
  await expect(page.getByTestId('app-header')).toBeVisible()
}

export async function upload(page: Page, file: string = PDFS.cot) {
  await page.getByTestId('file-input').setInputFiles(file)
  await expect(page.getByTestId('doc-pages')).toBeVisible({ timeout: 30_000 })
}

export function answer(page: Page): Locator {
  return page.getByTestId('answer').last()
}

export async function waitDone(page: Page) {
  await expect(answer(page)).toHaveAttribute('data-phase', /done|error/, { timeout: 30_000 })
}

/** Ask a demo question by clicking its suggestion chip. */
export async function askDemo(page: Page, qid: string, opts: AskOpts = {}) {
  await routeAsk(page, opts)
  await page.getByTestId(`suggest-${qid}`).click()
  await waitDone(page)
}

/** Ask free text (used with forced fixtures). */
export async function askText(page: Page, text: string, opts: AskOpts = {}) {
  await routeAsk(page, opts)
  await page.getByTestId('question-input').fill(text)
  await page.getByTestId('ask-button').click()
  await waitDone(page)
}

export async function componentTypes(page: Page): Promise<string[]> {
  return page.getByTestId('component').evaluateAll((els) => els.map((e) => e.getAttribute('data-type') ?? ''))
}

/** A syntactically valid PDF with n blank pages (for the page-limit test). */
export function makePdf(pages: number): Buffer {
  const objs: string[] = []
  const kids = Array.from({ length: pages }, (_, i) => `${3 + i} 0 R`).join(' ')
  objs.push('<< /Type /Catalog /Pages 2 0 R >>')
  objs.push(`<< /Type /Pages /Kids [${kids}] /Count ${pages} >>`)
  for (let i = 0; i < pages; i++) objs.push('<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>')
  let out = '%PDF-1.4\n'
  const offsets: number[] = []
  objs.forEach((o, i) => {
    offsets.push(Buffer.byteLength(out))
    out += `${i + 1} 0 obj\n${o}\nendobj\n`
  })
  const xref = Buffer.byteLength(out)
  out += `xref\n0 ${objs.length + 1}\n0000000000 65535 f \n`
  for (const off of offsets) out += `${String(off).padStart(10, '0')} 00000 n \n`
  out += `trailer\n<< /Size ${objs.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`
  return Buffer.from(out, 'latin1')
}

/** View, model and language live in the header's options menu: open it if it is closed. */
export async function openMenu(page: Page) {
  const menu = page.getByTestId('menu')
  if (!(await menu.isVisible())) await page.getByTestId('menu-button').click()
  await expect(menu).toBeVisible()
}
