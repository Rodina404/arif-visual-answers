import { answer, askDemo, askText, componentTypes, expect, open, test, upload } from '../helpers/fixtures'

test.describe('restraint', () => {
  test.beforeEach(async ({ page }) => {
    await open(page)
    await upload(page)
  })

  test('q4 (who are the authors) is text only', async ({ page }) => {
    await askDemo(page, 'q4')
    await expect(page.getByTestId('answer-text')).toContainText('Jason Wei')
    await expect(answer(page).getByTestId('components')).toHaveCount(0)
    await expect(page.getByTestId('component')).toHaveCount(0)
  })

  test('five components are capped at three with the quiz last', async ({ page }) => {
    await askText(page, 'too many', { fixture: 'malformed/too_many' })
    expect(await componentTypes(page)).toEqual(['comparison', 'steps', 'quiz'])
    await expect(page.getByTestId('dropped-note')).toHaveCount(0)
  })

  test('needs_visual=false drops components', async ({ page }) => {
    await askText(page, 'no visual', { fixture: 'malformed/needs_visual_false_with_components' })
    await expect(page.getByTestId('component')).toHaveCount(0)
    await expect(page.getByTestId('answer-text')).toBeVisible()
  })

  test('the text-only toggle asks for no visuals', async ({ page }) => {
    await page.getByTestId('text-only').check()
    await askDemo(page, 'q1')
    await expect(page.getByTestId('component')).toHaveCount(0)
    await expect(page.getByTestId('answer-text')).not.toBeEmpty()
  })
})
