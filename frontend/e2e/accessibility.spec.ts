import { expect, test } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

test.describe('research workspace', () => {
  test('supports keyboard navigation between functional workspaces', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByRole('heading', { name: /From research question/i })).toBeVisible()

    const navigation = page.getByRole('navigation', { name: 'Research workspaces' })
    await expect(navigation).toBeVisible()

    const agenda = navigation.getByRole('button', { name: 'Research agenda' })
    await agenda.focus()
    await expect(agenda).toBeFocused()
    await page.keyboard.press('Enter')
    await expect(page.getByRole('heading', { name: 'Define a research mission' })).toBeVisible()

    await navigation.getByRole('button', { name: 'Literature explorer' }).click()
    await expect(page.getByRole('heading', { name: 'Find scholarly metadata' })).toBeVisible()

    await navigation.getByRole('button', { name: 'Knowledge graph' }).click()
    await expect(page.getByRole('heading', { name: 'Build a traceable concept graph' })).toBeVisible()

    await navigation.getByRole('button', { name: 'Hypothesis lab' }).click()
    await expect(page.getByRole('heading', { name: 'Develop competing explanations' })).toBeVisible()

    await navigation.getByRole('button', { name: 'Computational lab' }).click()
    await expect(page.getByRole('heading', { name: 'Run a controlled computational experiment' })).toBeVisible()
    await expect(page.getByText(/does not execute arbitrary code/i)).toBeVisible()

    await navigation.getByRole('button', { name: 'Experiment journal' }).click()
    await expect(page.getByRole('heading', { name: 'Inspect the computational evidence trail' })).toBeVisible()
    await expect(page.getByText(/does not prove a scientific claim/i)).toBeVisible()

    await navigation.getByRole('button', { name: 'Scientific memory' }).click()
    await expect(page.getByRole('heading', { name: 'Maintain evidence-linked research memory' })).toBeVisible()
    await expect(page.getByText(/does not confer scientific validity/i)).toBeVisible()

    await navigation.getByRole('button', { name: 'Manuscript studio' }).click()
    await expect(page.getByRole('heading', { name: 'Prepare an evidence-linked research draft' })).toBeVisible()
    await expect(page.getByText(/This studio creates research drafts only/i)).toBeVisible()

    await navigation.getByRole('button', { name: 'Data analysis' }).click()
    await expect(page.getByRole('heading', { name: 'Explore numerical evidence' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Analyze a numeric sample' })).toBeVisible()

    await navigation.getByRole('button', { name: 'Mathematics workbench' }).click()
    await expect(page.getByRole('heading', { name: 'Run a bounded symbolic calculation' })).toBeVisible()
  })

  test('states which capabilities and external boundaries are actually available', async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('.workspace-stat').nth(1).locator('strong')).toContainText('11')
    await expect(page.getByText('Not connected', { exact: true })).toBeVisible()
    await expect(page.getByText(/hypothesis suggestions use deterministic templates/i)).toBeVisible()
    await expect(page.getByText(/identity, sandbox deployment, operations and external scientific review remain open/i)).toBeVisible()

    await page.getByRole('button', { name: 'Knowledge graph' }).click()
    await expect(page.getByRole('heading', { name: 'Build a traceable concept graph' })).toBeVisible()
    await expect(page.getByText(/proposed links are not scientific facts/i)).toBeVisible()

    await page.getByRole('button', { name: 'Research records' }).click()
    await expect(page.getByRole('heading', { name: 'Research records' })).toBeVisible()
    await expect(page.getByText(/content SHA-256 digest/i)).toBeVisible()
  })

  test('has no automated WCAG violations in the command center', async ({ page }) => {
    await page.goto('/')
    const results = await new AxeBuilder({ page }).analyze()
    expect(results.violations).toEqual([])
  })
})
