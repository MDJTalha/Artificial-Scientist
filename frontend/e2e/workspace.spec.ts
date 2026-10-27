import { expect, test } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/health', async route => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'ok', service: 'Artificial Scientist', version: '0.1.0' }),
    })
  })
})

test('keyboard users can skip navigation and reach the main workspace', async ({ page }) => {
  await page.goto('/')
  const skipLink = page.getByRole('link', { name: 'Skip to main content' })
  await page.keyboard.press('Tab')
  await expect(skipLink).toBeFocused()
  await expect(skipLink).toBeVisible()
  await page.keyboard.press('Enter')
  await expect(page.locator('#main-content')).toBeFocused()
})

test('navigation exposes the active section and keyboard-operable controls', async ({ page }) => {
  await page.goto('/')
  const navigation = page.getByRole('navigation', { name: 'Main navigation' })
  const literature = navigation.getByRole('button', { name: /Literature search/ })
  await literature.focus()
  await expect(literature).toBeFocused()
  await page.keyboard.press('Enter')
  await expect(literature).toHaveAttribute('aria-current', 'page')
  await expect(page.getByRole('heading', { name: 'Search the literature' })).toBeVisible()
})

test('literature form reports a real mocked provider error accessibly', async ({ page }) => {
  await page.route('**/api/v1/literature/search', async route => {
    await route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'Provider temporarily unavailable' }),
    })
  })
  await page.goto('/')
  await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('button', { name: /Literature search/ }).click()
  await page.getByRole('textbox', { name: 'Research query' }).fill('test query for science')
  await page.getByRole('button', { name: /Search scholarly sources/ }).click()
  await expect(page.getByRole('alert')).toContainText('HTTP 503')
  await expect(page.getByRole('alert')).toContainText('Provider temporarily unavailable')
})

test('record listing displays server data and preserves an empty/error distinction', async ({ page }) => {
  await page.route('**/api/v1/records?**', async route => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: [{ id: 'record-1', record_type: 'research_task', created_at: '2026-01-01T00:00:00Z', payload: { title: 'Verified test record' } }],
        total: 1,
      }),
    })
  })
  await page.goto('/')
  await page.getByRole('button', { name: /Research records/ }).first().click()
  await page.getByRole('button', { name: 'Load records' }).click()
  await expect(page.getByRole('row', { name: /Verified test record/ })).toBeVisible()
  await expect(page.getByText('1 TOTAL', { exact: true })).toBeVisible()
})

test('critical and serious accessibility rules have no violations on primary sections', async ({ page }) => {
  await page.goto('/')
  for (const section of ['overview', 'literature', 'records', 'knowledge', 'math', 'lab']) {
    if (section !== 'overview') {
      const buttonNames: Record<string, RegExp> = {
        literature: /Literature search/,
        records: /Research records/,
        knowledge: /Knowledge graph/,
        math: /Mathematics lab/,
        lab: /Controlled lab/,
      }
      await page.getByRole('button', { name: buttonNames[section] }).first().click()
    }
    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
      .analyze()
    const serious = results.violations.filter(v => v.impact === 'critical' || v.impact === 'serious')
    expect(serious, `Accessibility violations in ${section}: ${JSON.stringify(serious.map(v => ({ id: v.id, nodes: v.nodes.map(n => n.target) }))) }`).toEqual([])
  }
})


test('workspace remains within common mobile, tablet, and desktop viewports', async ({ page }) => {
  await page.goto('/')
  for (const viewport of [
    { width: 320, height: 720 },
    { width: 390, height: 844 },
    { width: 768, height: 1024 },
    { width: 1280, height: 720 },
    { width: 1440, height: 900 },
  ]) {
    await page.setViewportSize(viewport)
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  }
})

test('successful API responses announce completion in a persistent live region', async ({ page }) => {
  await page.route('**/api/v1/knowledge/vocabulary', async route => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ terms: ['hypothesis', 'evidence'] }),
    })
  })
  await page.goto('/')
  await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('button', { name: /Knowledge graph/ }).click()
  await page.getByRole('button', { name: 'View supported vocabulary' }).click()
  await expect(page.getByRole('status').filter({ hasText: 'Request completed' })).toBeAttached()
  await expect(page.getByRole('status').filter({ hasText: 'Request completed' })).toHaveCSS('position', 'absolute')
  await expect(page.getByRole('status').filter({ hasText: 'Request completed' })).toHaveCSS('width', '1px')
  await expect(page.getByRole('region', { name: 'Knowledge API response' })).toBeVisible()
})


test('skip-link target keeps a visible focus indicator and navigation works with Space', async ({ page }) => {
  await page.goto('/')
  const skipLink = page.getByRole('link', { name: 'Skip to main content' })
  await page.keyboard.press('Tab')
  await expect(skipLink).toBeFocused()
  await page.keyboard.press('Enter')
  const main = page.locator('#main-content')
  await expect(main).toBeFocused()
  await expect(main).toHaveCSS('outline-style', 'solid')
  await expect(main).toHaveCSS('outline-width', '3px')

  const navigation = page.getByRole('navigation', { name: 'Main navigation' })
  const knowledge = navigation.getByRole('button', { name: /Knowledge graph/ })
  await knowledge.focus()
  await page.keyboard.press('Space')
  await expect(knowledge).toHaveAttribute('aria-current', 'page')
  await expect(page.locator('#main-content').getByRole('heading', { name: 'Knowledge graph' })).toBeVisible()
})
