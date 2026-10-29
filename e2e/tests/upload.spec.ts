import { expect, makePdf, open, PDFS, test, upload } from '../helpers/fixtures'

test.describe('upload', () => {
  test.beforeEach(async ({ page }) => open(page))

  test('cot.pdf shows its page count', async ({ page }) => {
    await upload(page, PDFS.cot)
    await expect(page.getByTestId('doc-pages')).toContainText('43')
    await expect(page.getByTestId('question-input')).toBeEnabled()
    await expect(page.getByTestId('warning')).toHaveCount(0)
  })

  test('a PNG renamed to .pdf is rejected without crashing', async ({ page }) => {
    await page.getByTestId('file-input').setInputFiles(PDFS.notpdf)
    await expect(page.getByTestId('upload-error')).toBeVisible()
    await expect(page.getByTestId('doc-info')).toHaveCount(0)
    await expect(page.getByTestId('app-header')).toBeVisible()
  })

  test('an oversize file is rejected with a clear message', async ({ page }) => {
    const big = Buffer.concat([Buffer.from('%PDF-1.4\n'), Buffer.alloc(21 * 1024 * 1024, 48)])
    await page.getByTestId('file-input').setInputFiles({ name: 'big.pdf', mimeType: 'application/pdf', buffer: big })
    await expect(page.getByTestId('upload-error')).toBeVisible()
    await expect(page.getByTestId('upload-error')).toContainText(/20 MB|too large/i)
  })

  test('a PDF over the page limit is rejected with a clear message', async ({ page }) => {
    await page.getByTestId('file-input').setInputFiles({ name: 'many.pdf', mimeType: 'application/pdf', buffer: makePdf(61) })
    await expect(page.getByTestId('upload-error')).toContainText('61 pages')
  })
})
