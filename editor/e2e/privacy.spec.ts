/**
 * 隐私功能真实界面冒烟测试。
 *
 * 使用完整页面和模拟后端验证文件树、资源管理器、图书馆与独立隐私页的入口、
 * 锁定筛选、按钮顺序以及隐私内容封面隐藏。
 */
import { expect, test } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.route('**/*', async (route) => {
    const request = route.request()
    const pathname = new URL(request.url()).pathname
    const responses: Record<string, unknown> = {
      '/health': 'ok',
      '/settings/models/status': { embedding: 'ready', rerank: 'ready' },
      '/settings/profile': {
        user_id: 'privacy-e2e-user', knowledge_dir: 'D:/Knowledge', active_library_id: 'default', knowledge_libraries: [],
      },
      '/knowledge/files': {
        tree: [
          { name: 'public.md', path: 'public.md', isDir: false, size: 64, indexStatus: 'indexed', graphStatus: 'graphed' },
          { name: 'private.png', path: 'private.png', isDir: false, size: 128, indexStatus: 'indexed', graphStatus: 'graphed' },
        ],
      },
      '/privacy': {
        privacy: [
          { privacy_id: 'p-file', user_id: 'privacy-e2e-user', library_id: 'default', target_type: 'knowledge_path', target_id: 'private.png', created_at: '' },
          { privacy_id: 'p-book', user_id: 'privacy-e2e-user', library_id: 'default', target_type: 'library_item', target_id: 'book-private', created_at: '' },
        ],
      },
      '/favorites': { favorites: [] },
      '/knowledge/trash': { entries: [] },
      '/library/tags': { tags: [] },
      '/library/items': {
        items: [{
          item_id: 'book-private', user_id: 'privacy-e2e-user', library_id: 'default', parent_id: '', item_type: 'book', content_type: 'knowledge_file',
          title: '隐私图书', display_title: '隐私图书', description: '不可展示为封面的描述', storage_path: '', source_path: 'private.png',
          source_url: '', source_name: 'private.png', source_mime: 'image/png', source_size: 128, source_mtime: '', source_exists: true,
          cover_mode: 'image', cover_asset_id: 'cover-1', cover_asset: { asset_id: 'cover-1', url: '/private-cover.png' }, sort_order: 0,
          index_status: 'indexed', graph_status: 'graphed', tags: [], child_count: 0, created_at: '', updated_at: '',
        }],
        parent: null,
        breadcrumbs: [],
      },
      '/sessions': [],
      '/sessions/observability/history': [],
      '/agent/token-usage': { interval: '5m', calls: [], buckets: [], sessions: [] },
      '/skills': { skills: [], count: 0 },
      '/todo/list': [],
      '/automation/list': [],
      '/git/status': { initialized: false, branches: [], remote_branches: [], remotes: [], changes: [], untracked: [], ignored: [] },
    }
    if (pathname in responses) {
      const body = responses[pathname]
      await route.fulfill({
        status: 200,
        contentType: typeof body === 'string' ? 'text/plain' : 'application/json',
        body: typeof body === 'string' ? body : JSON.stringify(body),
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
      userId: 'privacy-e2e-user', knowledgeDir: 'D:/Knowledge', activeLibraryId: 'default', knowledgeLibraries: [],
    }))
    localStorage.setItem('agent_editor_show_index_column', 'true')
    localStorage.setItem('agent_editor_show_graph_column', 'true')
    localStorage.setItem('agent_editor_show_favorite_column', 'true')
    localStorage.setItem('agent_editor_show_privacy_column', 'true')
  })
})

test('renders every privacy entry, locked page, and cover protection', async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 1000 })
  await page.goto('/')
  await page.getByRole('button', { name: '进入文件', exact: true }).click()

  const treeRow = page.locator('.tree-root .file-item').filter({ hasText: 'private.png' })
  await expect(treeRow).toHaveCount(0)
  const publicTreeRow = page.locator('.tree-root .file-item').filter({ hasText: 'public.md' })
  await expect(publicTreeRow).toBeVisible()
  await publicTreeRow.click({ button: 'right' })
  const treeMenuActions = page.locator('.context-menu > button')
  const treeMenuLabels = (await treeMenuActions.allTextContents()).map((label) => label.trim())
  expect(treeMenuLabels.indexOf('隐私化')).toBe(treeMenuLabels.indexOf('收藏') + 1)
  await page.keyboard.press('Escape')
  const treeFavorite = page.locator('.header-row-secondary [title="我的收藏"]')
  const treePrivacy = page.locator('.header-row-secondary [title="我的隐私"]')
  expect(await treeFavorite.evaluate((element) => element.compareDocumentPosition(document.querySelector('.header-row-secondary [title="我的隐私"]')!))).toBe(4)
  await expect(treePrivacy).toBeVisible()
  await treePrivacy.click()
  await expect(treeRow.locator('.privacy-button')).toBeVisible()

  const activityBar = page.locator('.activity-bar')
  await expect(page.locator('.resource-row').filter({ hasText: 'private.png' })).toHaveCount(0)
  const publicResourceRow = page.locator('.resource-row').filter({ hasText: 'public.md' })
  await expect(publicResourceRow).toBeVisible()
  await publicResourceRow.click({ button: 'right' })
  const resourceMenuLabels = (await page.locator('.context-menu > button').allTextContents()).map((label) => label.trim())
  expect(resourceMenuLabels.indexOf('隐私化')).toBe(resourceMenuLabels.indexOf('收藏') + 1)
  await page.keyboard.press('Escape')
  await page.locator('.resource-toolbar').getByRole('button', { name: '我的隐私', exact: true }).click()
  await expect(page.locator('.resource-row').filter({ hasText: 'private.png' })).toBeVisible()

  await activityBar.getByRole('button', { name: '库', exact: true }).click()
  await expect(activityBar.getByRole('button', { name: '图书馆', exact: true })).toBeVisible()
  await activityBar.getByRole('button', { name: '图书馆', exact: true }).evaluate((button: HTMLButtonElement) => button.click())
  await expect(page.locator('.library-card').filter({ hasText: '隐私图书' })).toHaveCount(0)
  await page.locator('.library-toolbar').getByRole('button', { name: '我的隐私', exact: true }).click()
  await expect(page.locator('.library-card').filter({ hasText: '隐私图书' })).toBeVisible()

  await activityBar.getByRole('button', { name: '我的隐私', exact: true }).click()
  const privacyTabs = page.locator('.favorites-switch-button')
  await expect(privacyTabs).toHaveCount(2)
  await expect(privacyTabs.nth(0)).toContainText('文件')
  await expect(privacyTabs.nth(1)).toContainText('图书馆')

  const resourceToolbar = page.locator('.resource-toolbar')
  const resourceFavorite = resourceToolbar.getByRole('button', { name: '我的收藏', exact: true })
  const resourcePrivacy = resourceToolbar.getByRole('button', { name: '我的隐私', exact: true })
  await expect(resourcePrivacy).toBeDisabled()
  expect((await resourceFavorite.boundingBox())!.x).toBeLessThan((await resourcePrivacy.boundingBox())!.x)
  await expect(page.locator('.list-header')).toContainText('隐私状态')
  await expect(page.locator('.resource-row').filter({ hasText: 'private.png' })).toBeVisible()

  await resourceToolbar.getByRole('button', { name: '大', exact: true }).click()
  const tile = page.locator('.icon-tile').filter({ hasText: 'private.png' })
  await expect(tile.locator('.tile-image')).toHaveCount(0)
  expect((await tile.locator('.tile-privacy').boundingBox())!.x).toBeLessThan((await tile.locator('.tile-favorite').boundingBox())!.x)

  await privacyTabs.nth(1).click()
  const libraryToolbar = page.locator('.library-toolbar')
  const libraryFavorite = libraryToolbar.getByRole('button', { name: '我的收藏', exact: true })
  const libraryPrivacy = libraryToolbar.getByRole('button', { name: '我的隐私', exact: true })
  await expect(libraryPrivacy).toBeDisabled()
  expect((await libraryFavorite.boundingBox())!.x).toBeLessThan((await libraryPrivacy.boundingBox())!.x)

  const card = page.locator('.library-card').filter({ hasText: '隐私图书' })
  await expect(card.locator('.privacy-cover')).toBeVisible()
  await expect(card.locator('.cover-image')).toHaveCount(0)
  expect((await card.locator('.library-privacy').boundingBox())!.x).toBeLessThan((await card.locator('.library-favorite').boundingBox())!.x)

  await libraryToolbar.getByTitle('切换为条形').click()
  const bar = page.locator('.library-bar').filter({ hasText: '隐私图书' })
  await expect(bar.locator('.thumb-image')).toHaveCount(0)
  await expect(bar.getByLabel('隐私内容不显示封面')).toBeVisible()
  expect((await bar.locator('.bar-privacy').boundingBox())!.x).toBeLessThan((await bar.locator('.bar-favorite').boundingBox())!.x)
})
