import { expect, test } from '@playwright/test'

// Unlike workspace.spec.ts, this test deliberately does not intercept API requests.
test('built frontend connects to the live backend and runs a real calculation', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('status').filter({ hasText: 'API CONNECTED' })).toBeVisible()

  await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('button', { name: /Mathematics lab/ }).click()
  await expect(page.getByRole('heading', { name: 'Mathematics workbench' })).toBeVisible()
  await page.getByRole('button', { name: 'Run calculation' }).click()

  const response = page.getByRole('region', { name: 'Calculation response' })
  await expect(response).toBeVisible()
  await expect(response).toContainText('differentiate')
  await expect(response).toContainText('6*x**2 + 4*x - 5')
})
