/**
 * Dashboard activity heatmap browser smoke test.
 *
 * Usage:
 * Run with Playwright to verify the real dashboard keeps its GitHub-style
 * geometry while the existing filter color and activity logic remain active.
 */

import { expect, test } from '@playwright/test'

const emptySummary = { total_score: 0, active_days: 0, current_streak: 0, peak_score: 0 }

test('renders the GitHub-style activity graph and preserves filter interaction', async ({ page }, testInfo) => {
  await page.route('**/*', async (route) => {
    const request = route.request()
    const pathname = new URL(request.url()).pathname
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
    if (pathname === '/activity/heatmap') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          timezone: 'Asia/Shanghai',
          start_date: '2025-08-09',
          end_date: '2026-08-14',
          days: [{
            date: '2026-08-14',
            score: 8,
            level: 3,
            event_count: 2,
            modules: { agent: { score: 5, event_count: 1 } },
            activities: [],
          }],
          summaries: {
            all: { total_score: 8, active_days: 1, current_streak: 1, peak_score: 8 },
            library: emptySummary,
            documents: emptySummary,
            knowledge: emptySummary,
            agent: { total_score: 5, active_days: 1, current_streak: 1, peak_score: 5 },
            tasks: emptySummary,
            other: emptySummary,
          },
        }),
      })
      return
    }
    if (pathname === '/settings/profile') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ user_id: 'e2e-user', knowledge_dir: 'D:/Knowledge', active_library_id: 'default', knowledge_libraries: [] }),
      })
      return
    }
    const emptyResponses: Record<string, unknown> = {
      '/favorites': { favorites: [] },
      '/knowledge/files': { tree: [] },
      '/sessions': [{
        session_id: 'e2e-session',
        user_id: 'e2e-user',
        session_name: 'E2E Session',
        created_at: '2026-08-14T08:00:00Z',
        updated_at: '2026-08-14T08:00:00Z',
      }],
      '/sessions/e2e-session/messages': [],
      '/sessions/observability/history': [],
      '/agent/token-usage': { interval: '5m', calls: [], buckets: [], sessions: [] },
      '/skills': { skills: [], count: 0 },
      '/todo/list': [],
      '/automation/list': [],
      '/library/items': { items: [] },
      '/git/status': {
        initialized: false,
        branches: [],
        remote_branches: [],
        remotes: [],
        changes: [],
        untracked: [],
        ignored: [],
      },
    }
    if (pathname in emptyResponses) {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(emptyResponses[pathname]) })
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
      userId: 'e2e-user',
      knowledgeDir: 'D:/Knowledge',
      activeLibraryId: 'default',
      knowledgeLibraries: [],
    }))
  })
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto('/')
  await page.getByRole('button', { name: 'Dashboard' }).click()

  const card = page.locator('.activity-card')
  await expect(card).toBeVisible()
  const cellCount = await card.locator('[data-slot="contribution-graph-block"]').count()
  expect(cellCount).toBeGreaterThanOrEqual(28)
  expect(cellCount).toBeLessThanOrEqual(364)
  expect(cellCount % 7).toBe(0)
  await expect(card.locator('.weekday-labels')).toHaveText('一三五')
  await expect(card.locator('.legend-cell')).toHaveCount(7)

  const firstCell = card.locator('[data-slot="contribution-graph-block"]').first()
  await expect(firstCell).toHaveCSS('width', '10px')
  await expect(firstCell).toHaveCSS('height', '10px')
  await expect(firstCell).toHaveCSS('border-radius', '2px')

  await card.locator('[data-filter="agent"]').click()
  await expect(card.locator('[data-filter="agent"]')).toHaveClass(/active/)
  await expect(card).toHaveAttribute('style', /--heat-color: #c98516/)
  await card.screenshot({ path: testInfo.outputPath('activity-heatmap.png') })
})
