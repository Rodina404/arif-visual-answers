import { answer, askDemo, componentTypes, expect, open, routeAsk, test, upload, waitDone } from '../helpers/fixtures'

test.describe('answer', () => {
  test.beforeEach(async ({ page }) => {
    await open(page)
    await upload(page)
  })

  test('q1 streams skeletons first, then comparison, steps and quiz last', async ({ page }) => {
    await routeAsk(page)
    await page.getByTestId('suggest-q1').click()
    await expect(page.getByTestId('thinking')).toBeVisible()
    await expect(page.getByTestId('skeleton').first()).toBeVisible()
    await waitDone(page)
    await expect(page.getByTestId('skeleton')).toHaveCount(0)
    expect(await componentTypes(page)).toEqual(['comparison', 'steps', 'quiz'])
    await expect(page.getByTestId('answer-text')).not.toBeEmpty()
  })

  test('the quiz gives feedback, an explanation and a page chip', async ({ page }) => {
    await askDemo(page, 'q1')
    const q = page.getByTestId('quiz-question').first()
    await q.getByRole('radio').first().check() // "9" is wrong for question 1
    const fb = q.getByTestId('quiz-feedback')
    await expect(fb).toHaveAttribute('data-correct', 'false')
    await expect(fb.getByTestId('citation-chip')).toBeVisible()
    await q.getByRole('radio').nth(1).check()
    await expect(fb).toHaveAttribute('data-correct', 'true')
  })

  test('flashcards flip with the keyboard', async ({ page }) => {
    await askDemo(page, 'q5')
    const card = page.getByTestId('flashcard').first()
    await expect(card).toHaveAttribute('aria-pressed', 'false')
    const front = await card.getByTestId('flashcard-text').textContent()
    await card.focus()
    await page.keyboard.press('Space')
    await expect(card).toHaveAttribute('aria-pressed', 'true')
    await expect(card.getByTestId('flashcard-text')).not.toHaveText(front ?? '')
    await page.keyboard.press('Enter')
    await expect(card).toHaveAttribute('aria-pressed', 'false')
  })

  test('the metrics strip shows time, tokens, cost and verification', async ({ page }) => {
    await askDemo(page, 'q1')
    const strip = answer(page).getByTestId('metrics-strip')
    await expect(strip.getByTestId('metric-cost')).toContainText('$')
    await expect(strip.getByTestId('metric-verified')).toContainText('3/3')
  })
})
