import { expect, test } from '@playwright/test'

// This test deliberately does not intercept API requests: both services must be live.
test('built frontend connects to the live backend and runs a real calculation', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('status').filter({ hasText: 'API CONNECTED' })).toBeVisible()

  await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('button', { name: /Mathematics lab/ }).click()
  await expect(page.getByRole('heading', { name: 'Mathematics workbench' })).toBeVisible()
  await page.getByLabel('Request body (JSON)').fill(JSON.stringify({
    operation: 'differentiate',
    expression: 'x**3 + 2*x**2 - 5*x',
    variable: 'x',
  }, null, 2))
  await page.getByRole('button', { name: /Run calculation/ }).click()

  const response = page.locator('section[aria-label="Calculation response"]')
  await expect(response).toBeVisible({ timeout: 10_000 })
  await expect(response).toContainText('3*x**2 + 4*x - 5')
})
