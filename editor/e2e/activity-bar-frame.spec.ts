/**
 * Activity-bar frame smoke tests.
 *
 * Usage:
 * Verifies both persisted sidebar modes render the queue-lane ring and the
 * requested mode-specific outer geometry in a real browser layout.
 */
import { expect, test } from '@playwright/test'

const profile = {
  user_id: 'e2e-user',
  knowledge_dir: 'D:/Knowledge',
  active_library_id: 'default',
  knowledge_libraries: [],
}

const scenarios = [
  { mode: 'icons', theme: 'light', background: 'rgb(10, 10, 10)', muted: 'rgb(157, 161, 177)', activeBackground: 'rgb(51, 156, 255)', activeText: 'rgb(255, 255, 255)', panelBorder: 'rgba(0, 0, 0, 0)', borderRadius: '20px', leftOffset: 12, rightOffset: 60, width: 48 },
  { mode: 'management', theme: 'light', background: 'rgb(10, 10, 10)', muted: 'rgb(157, 161, 177)', activeBackground: 'rgb(244, 244, 246)', activeText: 'rgb(23, 23, 33)', panelBorder: 'rgba(0, 0, 0, 0)', borderRadius: '0px 28px 28px 0px', leftOffset: -4, rightOffset: 200, width: 204 },
  { mode: 'icons', theme: 'dark', background: 'rgb(18, 18, 20)', muted: 'rgb(143, 147, 163)', activeBackground: 'rgb(51, 156, 255)', activeText: 'rgb(255, 255, 255)', panelBorder: 'rgba(255, 255, 255, 0.12)', borderRadius: '20px', leftOffset: 12, rightOffset: 60, width: 48 },
  { mode: 'management', theme: 'dark', background: 'rgb(18, 18, 20)', muted: 'rgb(143, 147, 163)', activeBackground: 'rgb(244, 244, 246)', activeText: 'rgb(23, 23, 33)', panelBorder: 'rgba(255, 255, 255, 0.12)', borderRadius: '0px 28px 28px 0px', leftOffset: -4, rightOffset: 200, width: 204 },
] as const

for (const { mode, theme, background, muted, activeBackground, activeText, panelBorder, borderRadius, leftOffset, rightOffset, width } of scenarios) {
  test(`${theme} ${mode} activity bar keeps its framed inverse shape`, async ({ page }) => {
    await page.route('**/*', async (route) => {
      const request = route.request()
      const url = new URL(request.url())
      if (url.pathname === '/health') {
        await route.fulfill({ status: 200, body: 'ok' })
        return
      }
      if (url.pathname === '/settings/models/status') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ embedding: 'ready', rerank: 'ready' }),
        })
        return
      }
      if (url.pathname === '/settings/profile') {
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(profile) })
        return
      }
      if (request.resourceType() === 'fetch' || request.resourceType() === 'xhr') {
        await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' })
        return
      }
      await route.continue()
    })
    await page.addInitScript(({ displayMode, themeMode }) => {
      localStorage.setItem('agent_editor_sidebar_display_mode', displayMode)
      localStorage.setItem('agent_editor_theme_mode', themeMode)
      localStorage.setItem('agent_editor_profile', JSON.stringify({
        userId: 'e2e-user',
        knowledgeDir: 'D:/Knowledge',
        activeLibraryId: 'default',
        knowledgeLibraries: [],
      }))
    }, { displayMode: mode, themeMode: theme })

    await page.goto('/')
    const activityBar = page.locator('.activity-bar')
    const workspaceGrid = page.locator('.workspace-grid')
    await expect(activityBar).toBeVisible()

    const frame = await activityBar.evaluate((element) => {
      const style = getComputedStyle(element)
      const bounds = element.getBoundingClientRect()
      return {
        borderWidth: style.borderWidth,
        borderRadius: style.borderRadius,
        boxShadow: style.boxShadow,
        background: style.backgroundColor,
        bounds: { top: bounds.top, bottom: bounds.bottom, left: bounds.left, right: bounds.right, width: bounds.width },
      }
    })
    const inactiveColor = await page.getByRole('button', { name: 'Files' }).evaluate((element) => getComputedStyle(element).color)
    const gridBounds = await workspaceGrid.evaluate((element) => {
      const bounds = element.getBoundingClientRect()
      return { top: bounds.top, bottom: bounds.bottom, left: bounds.left }
    })

    expect(frame.borderWidth).toBe('1px')
    expect(frame.boxShadow).toContain('4px')
    expect(frame.background).toBe(background)
    expect(inactiveColor).toBe(muted)
    expect(frame.borderRadius).toBe(borderRadius)
    expect(frame.bounds.top).toBe(gridBounds.top + 12)
    expect(frame.bounds.bottom).toBe(gridBounds.bottom - 12)
    expect(frame.bounds.left).toBe(gridBounds.left + leftOffset)
    expect(frame.bounds.right).toBe(gridBounds.left + rightOffset)
    expect(frame.bounds.width).toBe(width)

    const workspaceFrames = await page.locator('.main-shell.ide-panel, .editor-sidebar-content, .agent-col').evaluateAll((elements) => (
      elements.map((element) => {
        const style = getComputedStyle(element)
        return { borderColor: style.borderColor, boxShadow: style.boxShadow }
      })
    ))
    expect(workspaceFrames).toHaveLength(3)
    expect(workspaceFrames.map(({ borderColor }) => borderColor)).toEqual(Array(3).fill(panelBorder))
    expect(workspaceFrames.every(({ boxShadow }) => boxShadow.includes('4px'))).toBe(true)

    await page.getByTitle('切换 Agent 面板').click()
    await page.getByTitle('待办').click()
    await expect(page.locator('.agent-col')).toHaveAttribute('aria-hidden', 'false')
    await page.getByRole('button', { name: '切换右侧 Git 面板' }).click()
    await page.getByRole('button', { name: '切换右侧 Git 面板' }).click()

    const agentButton = page.getByRole('button', { name: 'Agent', exact: true })
    await agentButton.click()
    await expect(agentButton).toHaveClass(/active/)
    await expect(agentButton).toHaveCSS('background-color', activeBackground)
    await expect(agentButton).toHaveCSS('color', activeText)
  })
}
