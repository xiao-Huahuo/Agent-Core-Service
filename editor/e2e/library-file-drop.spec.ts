/**
 * 图书馆文件拖放与图片封面真实浏览器验收。
 *
 * 使用说明：在真实 Vue 页面中验证外部图片拖放、新建表单提示、编辑表单封面模式，
 * 并输出桌面、平板、移动和超窄四档截图供视觉验收。
 */

import { expect, test, type Page } from '@playwright/test'

const screenshotDirectory = '../docs/screenshots/library-file-drop'

/** 构造图书馆页面所需的稳定接口数据，同时保留真实组件和交互。 */
async function mockLibraryWorkspace(page: Page): Promise<void> {
  const textBook = {
    item_id: 'text-book', user_id: 'library-drop-smoke', library_id: 'default', parent_id: '', item_type: 'book',
    content_type: 'knowledge_file', title: '普通文档', display_title: '普通文档', description: '',
    storage_path: '.mw/library/普通文档.md', source_path: '.mw/library/普通文档.md', source_url: '',
    source_name: '普通文档.md', source_mime: 'text/markdown', source_size: 12, source_mtime: '2026-08-27T12:00:00Z', source_exists: true,
    cover_mode: 'title', cover_asset_id: '', cover_asset: null, sort_order: 0, index_status: '', graph_status: '',
    tags: [], child_count: 0, created_at: '2026-08-27T12:00:00Z', updated_at: '2026-08-27T12:00:00Z',
  }
  const items = [textBook]

  await page.route('**/*', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const json = (body: unknown) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })

    if (url.pathname === '/health') return route.fulfill({ status: 200, contentType: 'text/plain', body: 'ok' })
    if (url.pathname === '/settings/models/status') return json({ embedding: 'ready', rerank: 'ready' })
    if (url.pathname === '/settings/profile') {
      return json({
        user_id: 'library-drop-smoke', knowledge_dir: 'D:/Knowledge', active_library_id: 'default',
        knowledge_libraries: [{ library_id: 'default', name: '图书馆验收库', knowledge_dir: 'D:/Knowledge', library_storage_dir: '.mw/library', is_active: true }],
      })
    }
    if (url.pathname === '/knowledge/files') return json({ tree: [] })
    if (url.pathname === '/knowledge/files/events') return route.fulfill({ status: 200, contentType: 'text/event-stream', body: ': smoke\n\n' })
    if (url.pathname === '/knowledge/files/upload' && request.method() === 'POST') {
      return json({ uploaded_path: 'D:/Knowledge/.mw/library/photo.jpeg', knowledge_dir: 'D:/Knowledge' })
    }
    if (url.pathname === '/library/items/book' && request.method() === 'POST') {
      const payload = request.postDataJSON() as Record<string, unknown>
      items.push({
        ...textBook,
        item_id: 'image-book',
        title: 'photo',
        display_title: 'photo',
        storage_path: '.mw/library/photo.jpeg',
        source_path: '.mw/library/photo.jpeg',
        source_name: 'photo.jpeg',
        source_mime: 'image/jpeg',
        cover_mode: String(payload.cover_mode),
      })
      return json({ item: items[items.length - 1] })
    }
    if (url.pathname === '/library/items' && request.method() === 'GET') return json({ items, parent: null, breadcrumbs: [] })
    if (url.pathname === '/library/tags') return json({ tags: [] })
    if (url.pathname === '/favorites') return json({ favorites: [] })
    if (url.pathname === '/privacy') return json({ privacy: [] })
    if (url.pathname === '/knowledge/files/raw') {
      return route.fulfill({
        status: 200,
        contentType: 'image/svg+xml',
        body: '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="500"><rect width="800" height="500" fill="#4224EB"/><circle cx="400" cy="250" r="130" fill="#EB2463"/></svg>',
      })
    }
    if (request.resourceType() === 'fetch' || request.resourceType() === 'xhr') return json({})
    return route.continue()
  })

  await page.addInitScript(() => {
    localStorage.setItem('agent_editor_profile', JSON.stringify({
      userId: 'library-drop-smoke', knowledgeDir: 'D:/Knowledge', activeLibraryId: 'default',
      knowledgeLibraries: [{ libraryId: 'default', name: '图书馆验收库', knowledgeDir: 'D:/Knowledge', libraryStorageDir: '.mw/library', isActive: true }],
    }))
  })
}

/** 从首页现有入口进入图书馆。 */
async function openLibrary(page: Page): Promise<void> {
  await page.getByRole('button', { name: /进入图书馆/u }).first().click()
  await expect(page.locator('.library-view')).toBeVisible()
}

/** 关闭与图书馆无关的外围侧栏，复现用户聚焦主页面时的正常可用宽度。 */
async function closePeripheralSidebars(page: Page): Promise<void> {
  if (await page.locator('.file-col').getAttribute('aria-hidden') === 'false') {
    await page.getByRole('button', { name: 'Files', exact: true }).click()
  }
  if (await page.locator('.todo-body-wrap').getAttribute('class').then((value) => value?.includes('visible'))) {
    await page.getByRole('button', { name: '待办', exact: true }).click()
  }
  if (await page.locator('.agent-section').getAttribute('class').then((value) => value?.includes('visible'))) {
    await page.getByTitle('切换 Agent 面板').click()
  }
  if (await page.getByRole('region', { name: '内置浏览器' }).isVisible()) {
    await page.getByRole('button', { name: '关闭右侧浏览器' }).click()
  }
}

/** 在浏览器页面内创建真实 File/DataTransfer 对象并派发拖放事件。 */
async function dispatchImageDrag(page: Page, type: 'dragenter' | 'dragleave' | 'drop'): Promise<void> {
  await page.locator('.library-view').evaluate((element, eventType) => {
    const transfer = new DataTransfer()
    transfer.items.add(new File(['image'], 'photo.jpeg', { type: 'image/jpeg' }))
    element.dispatchEvent(new DragEvent(eventType, { bubbles: true, cancelable: true, dataTransfer: transfer }))
  }, type)
}

/** 返回能识别截断、横向溢出或掉出页面的关键几何信号。 */
async function libraryGeometry(page: Page) {
  return page.locator('.library-view').evaluate((view) => {
    const root = view.getBoundingClientRect()
    const dialog = document.querySelector<HTMLElement>('.dialog-panel')
    const dialogBox = dialog?.getBoundingClientRect()
    return {
      pageOverflow: view.scrollWidth - view.clientWidth,
      dialogOverflow: dialog ? dialog.scrollWidth - dialog.clientWidth : 0,
      dialogInside: !dialogBox || (dialogBox.left >= 0 && dialogBox.right <= window.innerWidth + 1 && dialogBox.top >= 0 && dialogBox.bottom <= window.innerHeight + 1),
      rootInside: root.left >= 0 && root.right <= window.innerWidth + 1,
    }
  })
}

test('creates an image book by drop and keeps all related UI responsive', async ({ page }) => {
  test.setTimeout(60_000)
  await mockLibraryWorkspace(page)
  await page.setViewportSize({ width: 1280, height: 900 })
  await page.goto('/')
  await openLibrary(page)
  await closePeripheralSidebars(page)

  await dispatchImageDrag(page, 'dragenter')
  await expect(page.locator('.library-file-drop-overlay')).toContainText('松开文件即可自动创建图书')
  await page.screenshot({ path: `${screenshotDirectory}/drop-overlay-desktop.png`, fullPage: true })
  await dispatchImageDrag(page, 'drop')
  await expect(page.locator('.library-card')).toHaveCount(2)
  await expect(page.locator('.library-card').filter({ hasText: 'photo' }).locator('.cover-image')).toBeVisible()

  await page.getByTitle('新增文件').click()
  await page.locator('.file-zone input[type="file"]').setInputFiles({ name: 'photo.jpeg', mimeType: 'image/jpeg', buffer: Buffer.from('image') })
  await expect(page.locator('.cover-zone')).toContainText('可选；未上传时使用原图')
  await expect(page.getByText('已从拖入文件创建图书', { exact: true })).toBeHidden({ timeout: 5_000 })

  const viewports = [
    { name: 'desktop', width: 1280, height: 900 },
    { name: 'tablet', width: 768, height: 900 },
    { name: 'mobile', width: 375, height: 812 },
    { name: 'narrow', width: 320, height: 760 },
  ] as const
  for (const viewport of viewports) {
    await page.setViewportSize({ width: viewport.width, height: viewport.height })
    const geometry = await libraryGeometry(page)
    expect(geometry.pageOverflow).toBeLessThanOrEqual(1)
    expect(geometry.dialogOverflow).toBeLessThanOrEqual(1)
    expect(geometry.dialogInside).toBe(true)
    expect(geometry.rootInside).toBe(true)
    await page.screenshot({ path: `${screenshotDirectory}/${viewport.name}.png`, fullPage: true })
  }

  await page.setViewportSize({ width: 1280, height: 900 })
  await page.getByRole('button', { name: '关闭', exact: true }).click()
  const imageCard = page.locator('.library-card').filter({ hasText: 'photo' })
  await imageCard.click({ button: 'right' })
  await page.locator('.context-item').filter({ hasText: '编辑' }).click()
  await expect(page.locator('.cover-options')).toContainText('使用真实图片')
  await expect(page.locator('.cover-options')).not.toContainText('上传图片')
  await page.screenshot({ path: `${screenshotDirectory}/edit-source-image.png`, fullPage: true })
  await page.getByRole('button', { name: '关闭', exact: true }).click()

  const textCard = page.locator('.library-card').filter({ hasText: '普通文档' })
  await textCard.click({ button: 'right' })
  await page.locator('.context-item').filter({ hasText: '编辑' }).click()
  await expect(page.locator('.cover-options')).toContainText('上传图片')
  await expect(page.locator('.cover-options')).not.toContainText('使用真实图片')
  await page.screenshot({ path: `${screenshotDirectory}/edit-upload-image.png`, fullPage: true })
})
