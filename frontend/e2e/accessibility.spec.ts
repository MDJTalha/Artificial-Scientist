import { expect, test } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

test.describe('conference-grade research workspace', () => {
  test('renders the governed overview and remains navigable by keyboard', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByRole('heading', { name: /Scientific discovery/i })).toBeVisible()
    await expect(page.getByRole('navigation', { name: 'Research workspace' })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Release gates' })).toBeVisible()
    await page.getByRole('link', { name: 'Release gates' }).focus()
    await expect(page.getByRole('link', { name: 'Release gates' })).toBeFocused()
    await page.keyboard.press('Enter')
    await expect(page.locator('#release-gates')).toBeInViewport()
    await expect(page.getByRole('heading', { name: /Open gates that CI cannot self-certify/i })).toBeVisible()
  })

  test('exposes explicit gated status rather than production-complete claims', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByText('Evidence-gated, not production-certified')).toBeVisible()
    await expect(page.getByText('RELEASE GATES ACTIVE')).toBeVisible()
    await expect(page.getByText('Controlled lab')).toBeVisible()
    await expect(page.getByText('GATED', { exact: true }).first()).toBeVisible()
  })

  test('has no automated WCAG violations in the rendered workspace', async ({ page }) => {
    await page.goto('/')
    const results = await new AxeBuilder({ page }).analyze()
    expect(results.violations).toEqual([])
  })
})
