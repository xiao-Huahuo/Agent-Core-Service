/**
 * Dashboard activity heatmap browser smoke test.
 *
 * Usage:
 * Run with Playwright to verify the real dashboard keeps its GitHub-style
 * geometry while the existing filter color and activity logic remain active.
 * It also guards the dashboard's desktop, tablet, and mobile layout flow.
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
      '/sessions/observability/history': [
        {
          session_id: 'e2e-session',
          message_id: 'e2e-user-message',
          role: 'user',
          content: '请分析知识库中多个来源的内容，并给出包含完整依据和处理步骤的详细回答。',
          metadata: {},
          created_at: '2026-08-14T08:00:00Z',
        },
        {
          session_id: 'e2e-session',
          message_id: 'e2e-assistant-message',
          role: 'assistant',
          content: '已完成分析。',
          metadata: {
            trace: [
              { node: 'planner', duration_ms: 1200 },
              { node: 'knowledge', duration_ms: 1800 },
              { node: 'action', duration_ms: 900 },
              { node: 'observation', duration_ms: 700 },
              { node: 'agent', duration_ms: 1600 },
            ],
          },
          created_at: '2026-08-14T08:00:07Z',
        },
      ],
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
  await expect(page.locator('.agent-session-list')).toHaveCount(0)
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
  await page.locator('.time-panel').screenshot({ path: testInfo.outputPath('dashboard.png') })

  await page.setViewportSize({ width: 1000, height: 900 })
  const upperRow = page.locator('.row-upper')
  const lowerRow = page.locator('.row-lower')
  await expect.poll(async () => {
    const [upper, lower] = await Promise.all([upperRow.boundingBox(), lowerRow.boundingBox()])
    return Boolean(upper && lower && upper.y + upper.height <= lower.y + 1)
  }).toBe(true)
  await expect.poll(async () => (await upperRow.boundingBox())?.height ?? 0).toBeGreaterThanOrEqual(239)
  await expect.poll(async () => (
    (await page.locator('.col-rag .dashboard-card-surface').boundingBox())?.height ?? 0
  )).toBeGreaterThan(190)
  await expect.poll(async () => page.locator('.gauges-row').evaluate((element) => (
    getComputedStyle(element).gridTemplateColumns.split(' ').length
  ))).toBe(3)
  await expect.poll(async () => {
    const [token, activity] = await Promise.all([
      page.locator('.col-token .dashboard-card').boundingBox(),
      page.locator('.planning-right .dashboard-card').boundingBox(),
    ])
    return Boolean(token && activity && token.y + token.height <= activity.y + 1)
  }).toBe(true)
  await page.screenshot({ path: testInfo.outputPath('dashboard-tablet-wide.png'), fullPage: true })

  await page.setViewportSize({ width: 768, height: 1024 })
  const ragColumn = page.locator('.col-rag')
  const tokenColumn = page.locator('.col-token')
  await expect.poll(async () => {
    const [rag, token] = await Promise.all([ragColumn.boundingBox(), tokenColumn.boundingBox()])
    return Boolean(rag && token && Math.abs(rag.x - token.x) <= 1 && rag.y + rag.height <= token.y + 1)
  }).toBe(true)
  await expect.poll(async () => (
    (await page.locator('.type-share-panel').boundingBox())?.height ?? Number.POSITIVE_INFINITY
  )).toBeLessThanOrEqual(260)
  const tabletDashboard = page.locator('.dashboard-view')
  await expect.poll(async () => page.locator('.col-latency .card-body').evaluate((element) => (
    element.scrollHeight <= element.clientHeight
  ))).toBe(true)
  await tabletDashboard.evaluate((element) => element.scrollTo({ top: 0 }))
  const tabletBox = await tabletDashboard.boundingBox()
  await page.mouse.move(
    (tabletBox?.x ?? 0) + (tabletBox?.width ?? 1) / 2,
    (tabletBox?.y ?? 0) + (tabletBox?.height ?? 1) / 2,
  )
  await page.mouse.wheel(0, 10000)
  await expect.poll(async () => tabletDashboard.evaluate((element) => (
    Math.ceil(element.scrollTop + element.clientHeight) >= element.scrollHeight
  ))).toBe(true)
  await page.screenshot({ path: testInfo.outputPath('dashboard-tablet-bottom.png'), fullPage: true })

  await page.setViewportSize({ width: 390, height: 844 })
  const dashboard = page.locator('.dashboard-view')
  await expect.poll(async () => dashboard.evaluate((element) => element.scrollHeight > element.clientHeight)).toBe(true)
  await expect.poll(async () => dashboard.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true)
  await expect.poll(async () => page.locator('.filter-rail').evaluate((rail) => {
    const railRect = rail.getBoundingClientRect()
    return [...rail.querySelectorAll('button')].every((button) => {
      const rect = button.getBoundingClientRect()
      return rect.left >= railRect.left - 1 && rect.right <= railRect.right + 1
    })
  })).toBe(true)
  await expect.poll(async () => page.locator('.metric-strip').evaluate((element) => (
    getComputedStyle(element).gridTemplateColumns.split(' ').length
  ))).toBe(2)
  await expect.poll(async () => page.locator('.col-latency .card-body').evaluate((element) => (
    element.scrollHeight <= element.clientHeight
  ))).toBe(true)
  await dashboard.evaluate((element) => element.scrollTo({ top: 0 }))
  const mobileBox = await dashboard.boundingBox()
  await page.mouse.move(
    (mobileBox?.x ?? 0) + (mobileBox?.width ?? 1) / 2,
    (mobileBox?.y ?? 0) + (mobileBox?.height ?? 1) / 2,
  )
  await page.mouse.wheel(0, 10000)
  await expect.poll(async () => dashboard.evaluate((element) => (
    Math.ceil(element.scrollTop + element.clientHeight) >= element.scrollHeight
  ))).toBe(true)
  await expect(page.locator('.col-latency')).toBeInViewport()
  await page.screenshot({ path: testInfo.outputPath('dashboard-mobile-bottom.png'), fullPage: true })
})
