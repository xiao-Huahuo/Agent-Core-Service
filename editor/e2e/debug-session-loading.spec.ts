/**
 * Debug page session loading browser regression.
 *
 * Usage:
 * Opens the real Debug view with an empty session backend and verifies that
 * the page performs one bounded refresh instead of continuously polling.
 */
import { expect, test } from '@playwright/test'

function waitForRequestWindow(milliseconds: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, milliseconds))
}

test('does not loop session requests when the Debug page has no sessions', async ({ page }) => {
  let sessionRequests = 0

  await page.route('**/*', async (route) => {
    const request = route.request()
    const pathname = new URL(request.url()).pathname
    if (pathname === '/sessions') {
      sessionRequests += 1
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
      return
    }
    if (pathname === '/health') {
      await route.fulfill({ status: 200, body: 'ok' })
      return
    }
    if (pathname === '/settings/models/status') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ embedding: 'ready', rerank: 'ready' }),
      })
      return
    }
    if (pathname === '/settings/profile') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          user_id: '1',
          knowledge_dir: 'D:/Knowledge',
          active_library_id: 'default',
          knowledge_libraries: [],
        }),
      })
      return
    }
    if (request.resourceType() === 'fetch' || request.resourceType() === 'xhr') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' })
      return
    }
    await route.continue()
  })

  await page.addInitScript(() => {
    localStorage.setItem('agent_editor_profile', JSON.stringify({
      userId: '1',
      knowledgeDir: 'D:/Knowledge',
      activeLibraryId: 'default',
      knowledgeLibraries: [],
    }))
  })

  await page.goto('/')
  const debugButton = page.getByRole('button', { name: 'Debug', exact: true })
  await expect(debugButton).toBeVisible()

  await debugButton.click()
  await expect(page.getByRole('button', { name: 'Agent 轨迹' })).toBeVisible()
  await waitForRequestWindow(1000)

  expect(sessionRequests).toBe(1)
})
