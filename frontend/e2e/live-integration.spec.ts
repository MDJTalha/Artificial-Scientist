import { expect, test } from '@playwright/test'

// This test deliberately does not intercept API requests: both services must be live.
test('built frontend connects to the live backend and runs a real calculation', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('status').filter({ hasText: 'API CONNECTED' })).toBeVisible()

  await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('button', { name: /Mathematics lab/ }).click()
  await expect(page.getByRole('heading', { name: 'Mathematics workbench' })).toBeVisible()
  await page.getByRole('button', { name: /Run calculation/ }).click()

  // The section is labelled for assistive technology but may not expose an implicit region role.
  const response = page.locator('section[aria-label="Calculation response"]')
  const error = page.getByRole('alert')
  await expect(response.or(error)).toBeVisible()
  await expect(error).toHaveCount(0)
  await expect(response).toContainText('3*x**2 + 4*x - 5')
})
