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

    await navigation.getByRole('button', { name: 'Review & governance' }).click()
    await expect(page.getByRole('heading', { name: 'Inspect governance evidence' })).toBeVisible()
    await expect(page.getByText(/Treat these entries as recorded assertions, not independent sign-off/i)).toBeVisible()
    await expect(page.getByText(/Requests only; no request is interpreted as an approval/i)).toBeVisible()

    await navigation.getByRole('button', { name: 'Data analysis' }).click()
    await expect(page.getByRole('heading', { name: 'Explore numerical evidence' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Analyze a numeric sample' })).toBeVisible()

    await navigation.getByRole('button', { name: 'Mathematics workbench' }).click()
    await expect(page.getByRole('heading', { name: 'Run a bounded symbolic calculation' })).toBeVisible()
  })

  test('states which capabilities and external boundaries are actually available', async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('.workspace-stat').nth(1).locator('strong')).toContainText('12')
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

  test('has no automated WCAG violations across all 12 workspace screens', async ({ page }) => {
    await page.goto('/')
    const navigation = page.getByRole('navigation', { name: 'Research workspaces' })
    const screens = [
      { label: 'Research agenda', heading: /Define a research mission/i },
      { label: 'Literature explorer', heading: /Find scholarly metadata/i },
      { label: 'Knowledge graph', heading: /Build a traceable concept graph/i },
      { label: 'Hypothesis lab', heading: /Develop competing explanations/i },
      { label: 'Computational lab', heading: /Run a controlled computational experiment/i },
      { label: 'Data analysis', heading: /Explore numerical evidence/i },
      { label: 'Experiment journal', heading: /Inspect the computational evidence trail/i },
      { label: 'Scientific memory', heading: /Maintain evidence-linked research memory/i },
      { label: 'Manuscript studio', heading: /Prepare an evidence-linked research draft/i },
      { label: 'Review & governance', heading: /Inspect governance evidence/i },
      { label: 'Mathematics workbench', heading: /Run a bounded symbolic calculation/i },
      { label: 'Research records', heading: /Research records/i },
    ]

    const commandCenter = await new AxeBuilder({ page }).analyze()
    expect(commandCenter.violations, 'Command Center accessibility violations').toEqual([])

    for (const screen of screens) {
      await navigation.getByRole('button', { name: screen.label }).click()
      await expect(page.getByRole('heading', { name: screen.heading })).toBeVisible()
      const results = await new AxeBuilder({ page }).analyze()
      expect(results.violations, screen.label + ' accessibility violations').toEqual([])
    }
  })
})
