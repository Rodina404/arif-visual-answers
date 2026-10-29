import { answer, askDemo, expect, open, PDFS, test, upload, waitDone } from '../helpers/fixtures'

test.describe('documents', () => {
  test('several PDFs: switch, per-document suggestions, answers and history, delete', async ({ page }) => {
    await open(page)
    await page.getByTestId('file-input').setInputFiles([PDFS.cot, PDFS.tiny])
    const items = page.getByTestId('doc-item')
    await expect(items).toHaveCount(2)
    // The last upload becomes active: not the demo paper, so no demo chips, generated suggestions instead.
    await expect(items.nth(1)).toHaveAttribute('data-active', 'true')
    await expect(page.getByTestId('suggest-q1')).toHaveCount(0)
    await expect(page.getByTestId('suggest-g1')).toBeVisible()

    // Switch to the CoT paper: its demo questions appear; ask one.
    await items.nth(0).locator('button').first().click()
    await expect(page.getByTestId('suggest-q1')).toBeVisible()
    await askDemo(page, 'q4')
    await expect(page.getByTestId('answer-text')).toContainText('Jason Wei')

    // Away and back: the CoT answer is restored, the tiny PDF has none.
    await items.nth(1).locator('button').first().click()
    await expect(page.getByTestId('answer')).toHaveCount(0)
    await items.nth(0).locator('button').first().click()
    await expect(page.getByTestId('answer-text')).toContainText('Jason Wei')

    // A second question puts the first one in this document's history.
    await askDemo(page, 'q1')
    await expect(page.getByTestId('history-item')).toHaveCount(1)
    await page.getByTestId('history-item').first().click()
    await waitDone(page)
    await expect(answer(page).getByTestId('answer-text')).toContainText('Jason Wei')

    // Delete the tiny PDF (two-step confirm).
    await items.nth(1).getByTestId('doc-delete').click()
    await items.nth(1).getByTestId('doc-delete-confirm').click()
    await expect(page.getByTestId('doc-item')).toHaveCount(1)

    // The list survives a reload (same browser), and another browser sees none of it.
    await page.reload()
    await expect(page.getByTestId('doc-item')).toHaveCount(1)
    await expect(page.getByTestId('doc-item').first()).toHaveAttribute('data-active', 'true')
  })

  test("another browser doesn't see my documents", async ({ page, browser }) => {
    await open(page)
    await upload(page, PDFS.tiny)
    const other = await browser.newPage()
    await other.goto('/')
    await expect(other.getByTestId('app-header')).toBeVisible()
    await expect(other.getByTestId('doc-item')).toHaveCount(0)
    await other.close()
  })
})
