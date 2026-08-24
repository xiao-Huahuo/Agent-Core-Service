/**
 * Appearance background cover browser smoke test.
 *
 * Usage:
 * Exercises the shared library uploader, persisted appearance request, live
 * application background, and reset path through the real settings UI.
 */
import { expect, test } from '@playwright/test'

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
  await page.screenshot({ path: testInfo.outputPath('appearance-background-applied.png'), fullPage: true })

  await page.getByRole('button', { name: '重置背景封面' }).click()
  await expect.poll(() => persistedBackground).toBe('')
  await expect.poll(() => page.evaluate(() => ({
    enabled: document.documentElement.hasAttribute('data-app-background-cover'),
    image: document.documentElement.style.getPropertyValue('--app-background-image'),
  }))).toEqual({ enabled: false, image: '' })
  expect(pageErrors).toEqual([])
})
