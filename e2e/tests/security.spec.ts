import fs from 'node:fs'
import path from 'node:path'
import { answer, askText, expect, INJECTION_Q, open, PDFS, ROOT, test, upload } from '../helpers/fixtures'

test.describe('security', () => {
  test('model HTML renders as literal text and never executes', async ({ page }) => {
    let dialogs = 0
    page.on('dialog', async (d) => {
      dialogs++
      await d.dismiss()
    })
    await open(page)
    await upload(page)
    await askText(page, 'html', { fixture: 'malformed/html_payload' })
    await expect(answer(page).getByText('<img src=x onerror=alert(1)>').first()).toBeVisible()
    await expect(answer(page).getByText(/<script>alert\(1\)<\/script>/).first()).toBeVisible()
    await expect(answer(page).locator('img, script, iframe')).toHaveCount(0)
    const hrefs = await page.locator('a').evaluateAll((as) => as.map((a) => a.getAttribute('href') ?? ''))
    expect(hrefs.every((h) => h === '/' || h === '/compare')).toBe(true)
    expect(dialogs).toBe(0)
  })

  test('the injection PDF warns, and the injected 99% is not verified', async ({ page, lang }) => {
    await open(page)
    await upload(page, PDFS.injection)
    await expect(page.locator('[data-testid="warning"][data-code="HIDDEN_TEXT_DETECTED"]').first()).toBeVisible()
    await askText(page, INJECTION_Q[lang])
    const chart = answer(page).locator('[data-component="chart"]')
    await expect(chart).toHaveAttribute('data-verification', 'partial')
    await expect(page.getByTestId('chart-point')).toHaveCount(3)
    await expect(page.getByTestId('chart-sources')).not.toContainText('99')
    expect(await page.content()).not.toContain('evil.example')
    expect(await page.locator('a[href*="evil"]').count()).toBe(0)
  })

  test('the CSP header is present on /', async ({ request }) => {
    const res = await request.get('/')
    const csp = res.headers()['content-security-policy']
    expect(csp).toContain("default-src 'self'")
    expect(csp).toContain("script-src 'self'")
    expect(csp).toContain("frame-ancestors 'none'")
    expect(res.headers()['x-content-type-options']).toBe('nosniff')
  })

  test('the built JS contains no API key', async () => {
    const dist = path.join(ROOT, 'frontend', 'dist')
    const files = fs.readdirSync(path.join(dist, 'assets')).filter((f) => f.endsWith('.js'))
    expect(files.length).toBeGreaterThan(0)
    const env = fs.existsSync(path.join(ROOT, '.env')) ? fs.readFileSync(path.join(ROOT, '.env'), 'utf-8') : ''
    const key = /GEMINI_API_KEY=(\S+)/.exec(env)?.[1]
    for (const f of [...files.map((x) => path.join(dist, 'assets', x)), path.join(dist, 'index.html')]) {
      const text = fs.readFileSync(f, 'utf-8')
      expect(text).not.toMatch(/AIza[0-9A-Za-z_-]{20,}/)
      if (key) expect(text.includes(key)).toBe(false)
    }
  })
})
