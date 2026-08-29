/**
 * Appearance background cover browser smoke test.
 *
 * Usage:
 * Exercises the shared library uploader, persisted appearance request, live
 * application background, and reset path through the real settings UI.
 */
import { expect, test, type Locator } from '@playwright/test'

/** Return whether one rendered surface has a transparent alpha channel. */
async function isTranslucent(locator: Locator) {
  return locator.evaluate((element) => {
    const color = getComputedStyle(element).backgroundColor
    const match = color.match(/(?:,|\/)\s*([\d.]+)\s*\)$/u)
    return color === 'transparent' || (match ? Number(match[1]) < 1 : false)
  })
}

test('uploads, applies, persists, and resets an application background cover', async ({ page }, testInfo) => {
  let persistedBackground = ''
  const pageErrors: string[] = []
  page.on('pageerror', (error) => pageErrors.push(error.message))
  await page.addInitScript(() => {
    localStorage.setItem('agent_editor_profile', JSON.stringify({
      userId: 'background-user', knowledgeDir: 'D:/Knowledge', activeLibraryId: 'default',
      knowledgeLibraries: [{ libraryId: 'default', name: 'Default', knowledgeDir: 'D:/Knowledge', isActive: true }],
      knowledgeWatchEnabled: true,
    }))
    localStorage.setItem('agent_editor_settings_active_tab', 'appearance')
  })
  await page.route('**/*', async (route) => {
    const request = route.request()
    if (!['fetch', 'xhr'].includes(request.resourceType())) return route.continue()
    const path = new URL(request.url()).pathname
    const json = (body: unknown) => route.fulfill({ json: body })
    if (path === '/health') return json({ ok: true })
    if (path === '/settings/models/status') return json({ embedding: 'ready', rerank: 'ready' })
    if (path === '/settings/profile') return json({
      user_id: 'background-user', knowledge_dir: 'D:/Knowledge', active_library_id: 'default',
      knowledge_libraries: [{ library_id: 'default', name: 'Default', knowledge_dir: 'D:/Knowledge', is_active: true }],
      theme_primary_color: '', theme_soft_color: '', background_cover_url: persistedBackground,
      show_backlinks: false, created_at: '', updated_at: '',
    })
    if (path === '/library/assets/cover') return json({ asset: {
      asset_id: 'asset-bg', mime_type: 'image/svg+xml', file_name: 'background.svg',
      url: '/library/assets/background-user/asset-bg.svg', width: 1200, height: 800, size: 120, created_at: '',
    } })
    if (path === '/settings/appearance/config') {
      const body = request.postDataJSON() as Record<string, unknown>
      if (typeof body.background_cover_url === 'string') persistedBackground = body.background_cover_url
      return json({
        user_id: 'background-user', theme_primary_color: '', theme_soft_color: '',
        background_cover_url: persistedBackground, show_backlinks: false, updated_at: '',
      })
    }
    if (path === '/favorites') return json({ favorites: [] })
    if (path === '/privacy') return json({ privacy: [] })
    if (path === '/sessions' || path === '/todo/list') return json([])
    if (path === '/knowledge/files') return json({ tree: [] })
    if (path === '/library/items') return json({ items: [], parent: null, breadcrumbs: [] })
    if (path === '/library/tags') return json({ tags: [] })
    if (path === '/component-library/components') return json({ components: [], count: 0 })
    if (path === '/smart-forms/list') return json({ forms: [] })
    if (path === '/agent-queue/tasks') return json({ tasks: [], settings: { max_concurrency: 5 } })
    if (path === '/skills') return json({ skills: [{
      skill_id: 'background-skill', name: 'Background Skill', description: 'Opaque card check',
      source: 'builtin', path: 'skills/background', enabled: true, metadata: {},
      has_scripts: false, has_references: false, has_assets: false,
    }], count: 1 })
    return json({})
  })
  await page.route('**/library/assets/background-user/asset-bg.svg', (route) => route.fulfill({
    contentType: 'image/svg+xml',
    body: '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="800"><defs><linearGradient id="g"><stop stop-color="#2d174f"/><stop offset="1" stop-color="#134e72"/></linearGradient></defs><rect width="1200" height="800" fill="url(#g)"/></svg>',
  }))

  await page.goto('/')
  await page.getByRole('button', { name: 'Settings' }).click()
  const uploader = page.locator('.background-cover-control .library-cover-uploader')
  await expect(uploader).toBeVisible()
  await uploader.locator('input[type="file"]').setInputFiles({
    name: 'background.svg',
    mimeType: 'image/svg+xml',
    buffer: Buffer.from('<svg xmlns="http://www.w3.org/2000/svg"/>'),
  })

  await expect.poll(() => persistedBackground).toBe('/library/assets/background-user/asset-bg.svg')
  await expect.poll(() => page.evaluate(() => ({
    enabled: document.documentElement.getAttribute('data-app-background-cover'),
    image: getComputedStyle(document.querySelector('#app') as HTMLElement).backgroundImage,
    cached: JSON.parse(localStorage.getItem('agent_editor_profile') || '{}').backgroundCoverUrl ?? '',
  }))).toEqual({
    enabled: 'true',
    image: expect.stringContaining('asset-bg.svg'),
    cached: '',
  })
  const transparency = await page.evaluate(() => {
    const host = document.createElement('div')
    host.style.position = 'fixed'
    host.style.left = '-10000px'
    const surfaces: Array<[string, string]> = [
      ['topbar', 'topbar'],
      ['fileColumn', 'file-col'],
      ['filePanel', 'file-panel'],
      ['libraryToolbar', 'library-toolbar'],
      ['componentToolbar', 'component-toolbar'],
      ['formsHeader', 'forms-header'],
      ['formsToolbar', 'forms-toolbar'],
      ['visualizationToolbar', 'visualization-toolbar'],
      ['resultHeader', 'result-header'],
      ['favoritesView', 'favorites-view'],
      ['favoritesBody', 'favorites-body'],
      ['skillCard', 'skill-card'],
    ]
    for (const [key, className] of surfaces) {
      const element = document.createElement('div')
      element.className = className
      element.dataset.bgSurface = key
      element.style.backgroundColor = 'rgb(10, 20, 30)'
      host.append(element)
    }
    const lane = document.createElement('div')
    lane.className = 'queue-lane'
    const laneCard = document.createElement('section')
    laneCard.dataset.bgSurface = 'queueLane'
    laneCard.style.backgroundColor = 'rgb(10, 20, 30)'
    lane.append(laneCard)
    host.append(lane)
    document.body.append(host)
    const inspectSurface = (key: string) => {
      const color = getComputedStyle(host.querySelector(`[data-bg-surface="${key}"]`) as HTMLElement).backgroundColor
      const match = color.match(/(?:,|\/)\s*([\d.]+)\s*\)$/u)
      return { color, translucent: color === 'transparent' || (match ? Number(match[1]) < 1 : false) }
    }
    const result = Object.fromEntries([...surfaces.map(([key]) => [key, inspectSurface(key)]), ['queueLane', inspectSurface('queueLane')]])
    host.remove()
    return result
  })
  expect(transparency).toMatchObject({
    topbar: { translucent: true },
    fileColumn: { translucent: true },
    filePanel: { translucent: true },
    libraryToolbar: { translucent: true },
    componentToolbar: { translucent: true },
    formsHeader: { translucent: true },
    formsToolbar: { translucent: true },
    queueLane: { translucent: true },
    favoritesView: { translucent: true },
    favoritesBody: { translucent: true },
    visualizationToolbar: { translucent: true },
    resultHeader: { translucent: true },
    skillCard: { translucent: false },
  })

  await expect.poll(() => isTranslucent(page.locator('.topbar'))).toBe(true)
  await expect.poll(() => isTranslucent(page.locator('.file-col'))).toBe(true)
  await expect.poll(() => isTranslucent(page.locator('.file-panel'))).toBe(true)
  await page.screenshot({ path: testInfo.outputPath('background-topbar-file-tree.png'), fullPage: true })

  const knowledgeButton = page.locator('.knowledge-button')
  await knowledgeButton.click()
  await page.locator('.knowledge-submenu .activity-button').nth(1).dispatchEvent('click')
  await expect.poll(() => isTranslucent(page.locator('.library-toolbar'))).toBe(true)
  await page.screenshot({ path: testInfo.outputPath('background-library-toolbar.png'), fullPage: true })

  await knowledgeButton.click()
  await page.locator('.knowledge-submenu .activity-button').nth(2).dispatchEvent('click')
  await expect.poll(() => isTranslucent(page.locator('.component-toolbar'))).toBe(true)
  await page.screenshot({ path: testInfo.outputPath('background-component-toolbar.png'), fullPage: true })

  await knowledgeButton.click()
  await page.locator('.knowledge-submenu .activity-button').nth(4).dispatchEvent('click')
  await expect.poll(() => isTranslucent(page.locator('.forms-header'))).toBe(true)
  await page.screenshot({ path: testInfo.outputPath('background-smart-forms-toolbar.png'), fullPage: true })

  const entertainmentButton = page.getByRole('button', { name: '娱乐功能' })
  await entertainmentButton.click()
  await page.getByRole('button', { name: '任务队列' }).click()
  await expect(page.locator('.queue-board .queue-lane > section')).toHaveCount(3)
  await expect.poll(async () => page.locator('.queue-board .queue-lane > section').evaluateAll((elements) => elements.every((element) => {
    const color = getComputedStyle(element).backgroundColor
    const match = color.match(/(?:,|\/)\s*([\d.]+)\s*\)$/u)
    return color === 'transparent' || (match ? Number(match[1]) < 1 : false)
  }))).toBe(true)
  await page.getByRole('button', { name: /历史/u }).click()
  await expect(page.locator('.history-list .queue-lane > section')).toHaveCount(2)
  await expect.poll(async () => page.locator('.history-list .queue-lane > section').evaluateAll((elements) => elements.every((element) => {
    const color = getComputedStyle(element).backgroundColor
    const match = color.match(/(?:,|\/)\s*([\d.]+)\s*\)$/u)
    return color === 'transparent' || (match ? Number(match[1]) < 1 : false)
  }))).toBe(true)
  await page.screenshot({ path: testInfo.outputPath('background-queue-cards.png'), fullPage: true })

  await page.getByRole('button', { name: '我的收藏' }).click()
  await expect.poll(() => isTranslucent(page.locator('.favorites-view'))).toBe(true)
  await page.screenshot({ path: testInfo.outputPath('background-favorites.png'), fullPage: true })
  await page.getByRole('button', { name: '我的隐私' }).click()
  await expect.poll(() => isTranslucent(page.locator('.favorites-view'))).toBe(true)
  await page.screenshot({ path: testInfo.outputPath('background-privacy.png'), fullPage: true })

  await entertainmentButton.click()
  await page.getByRole('button', { name: 'MD-HTML' }).click()
  await expect.poll(() => isTranslucent(page.locator('.visualization-toolbar'))).toBe(true)
  await page.screenshot({ path: testInfo.outputPath('background-md-html-toolbar.png'), fullPage: true })

  await page.getByRole('button', { name: 'Skills' }).click()
  await expect(page.locator('.skill-card')).toHaveCount(1)
  await expect.poll(() => isTranslucent(page.locator('.skill-card'))).toBe(false)
  await page.screenshot({ path: testInfo.outputPath('background-skills-opaque.png'), fullPage: true })
  await page.screenshot({ path: testInfo.outputPath('appearance-background-applied.png'), fullPage: true })

  await page.getByRole('button', { name: 'Settings' }).click()
  await page.getByRole('button', { name: '重置背景封面' }).click()
  await expect.poll(() => persistedBackground).toBe('')
  await expect.poll(() => page.evaluate(() => ({
    enabled: document.documentElement.hasAttribute('data-app-background-cover'),
    image: document.documentElement.style.getPropertyValue('--app-background-image'),
  }))).toEqual({ enabled: false, image: '' })
  expect(pageErrors).toEqual([])
})
