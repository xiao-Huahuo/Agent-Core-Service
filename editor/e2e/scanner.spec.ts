/**
 * Scanner page visual and interaction smoke test.
 *
 * Uses deterministic network fixtures around the real Vue components, then
 * captures the requested 1024/768/480 layouts and exercises upload-to-result.
 */
import { expect, test, type Page } from '@playwright/test'

const screenshotDirectory = '../docs/screenshots/scanner'

/** Install the smallest stable backend contract needed by the scanner page. */
async function mockScannerWorkspace(page: Page): Promise<void> {
  let uploadedAt = 0
  const record = (status: 'running' | 'finished') => ({
    scan_id: 'scan-smoke', user_id: 'scanner-smoke', library_id: 'default', source_kind: 'file',
    source_name: '课堂笔记.txt', source_path: '.mw/scan/scan-smoke/source/课堂笔记.txt', source_url: '', size: 28,
    ocr_enabled: true, status, stage: status === 'running' ? 'extract' : 'completed',
    stage_label: status === 'running' ? '正在解析文件内容' : '解析完成', progress: status === 'running' ? 44 : 100,
    no_ocr_markdown: status === 'finished' ? '# No OCR\n\n原始文字' : '',
    ocr_markdown: status === 'finished' ? '# OCR\n\n识别文字' : '', assets: [], error: '',
    source_text: status === 'finished' ? '课堂原始内容' : null,
    created_at: '2026-09-08T06:20:00Z', updated_at: '2026-09-08T06:21:00Z',
    finished_at: status === 'finished' ? '2026-09-08T06:21:00Z' : null,
  })

  await page.route('**/*', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const json = (body: unknown) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
    if (url.pathname === '/health') return route.fulfill({ status: 200, contentType: 'text/plain', body: 'ok' })
    if (url.pathname === '/settings/models/status' || url.pathname === '/settings/models/management') return json({ models: [] })
    if (url.pathname === '/settings/profile') return json({
      user_id: 'scanner-smoke', knowledge_dir: 'D:/Knowledge', active_library_id: 'default', editor_image_assets_dir: './assets/',
      knowledge_libraries: [{ library_id: 'default', name: '扫描验收库', knowledge_dir: 'D:/Knowledge', library_storage_dir: '.mw/library', is_active: true }],
    })
    if (url.pathname === '/knowledge/files') return json({ tree: [] })
    if (url.pathname === '/knowledge/files/events') return route.fulfill({ status: 200, contentType: 'text/event-stream', body: ': smoke\n\n' })
    if (url.pathname === '/sessions' || url.pathname === '/todo/list' || url.pathname === '/automation/list') return json([])
    if (url.pathname === '/favorites') return json({ favorites: uploadedAt ? [{ favorite_id: 'fav-scan', user_id: 'scanner-smoke', library_id: 'default', target_type: 'scanner', target_id: 'scan-smoke', created_at: '2026-09-08T06:22:00Z' }] : [] })
    if (url.pathname === '/privacy') return json({ privacy: [] })
    if (url.pathname === '/scanner/files' && request.method() === 'POST') { uploadedAt = Date.now(); return json(record('running')) }
    if (url.pathname === '/scanner' && request.method() === 'GET') return json({ scans: uploadedAt ? [record(Date.now() - uploadedAt > 1_000 ? 'finished' : 'running')] : [] })
    if (url.pathname === '/scanner/scan-smoke' && request.method() === 'GET') return json(record(Date.now() - uploadedAt > 1_000 ? 'finished' : 'running'))
    if (url.pathname.endsWith('/draft') || url.pathname.endsWith('/source')) return json(record('finished'))
    if (request.resourceType() === 'fetch' || request.resourceType() === 'xhr') return json({})
    return route.continue()
  })
  await page.addInitScript(() => localStorage.setItem('agent_editor_profile', JSON.stringify({
    userId: 'scanner-smoke', knowledgeDir: 'D:/Knowledge', activeLibraryId: 'default',
    knowledgeLibraries: [{ libraryId: 'default', name: '扫描验收库', knowledgeDir: 'D:/Knowledge', libraryStorageDir: '.mw/library', isActive: true }],
  })))
}

/** Open scanner through the real grouped activity navigation. */
async function openScanner(page: Page): Promise<void> {
  await page.getByRole('button', { name: '库', exact: true }).click()
  await page.getByRole('button', { name: '扫描器', exact: true }).click()
  await expect(page.locator('.scanner-view')).toBeVisible()
}

/** Assert the scanner root does not introduce horizontal overflow. */
async function expectNoScannerOverflow(page: Page): Promise<void> {
  const overflow = await page.locator('.scanner-view').evaluate((element) => element.scrollWidth - element.clientWidth)
  expect(overflow).toBeLessThanOrEqual(1)
}

test('scanner upload, result editing, examples, and responsive layouts', async ({ page }) => {
  test.setTimeout(60_000)
  await mockScannerWorkspace(page)
  await page.setViewportSize({ width: 1024, height: 820 })
  await page.goto('/')
  await openScanner(page)

  await expect(page.locator('.scanner-example')).toHaveCount(7)
  await expect(page.getByRole('button', { name: /上传文件/u })).toBeVisible()
  const uploadGeometry = await page.locator('.scanner-drop-zone').evaluate((zone) => {
    const button = zone.querySelector('button:not(.scanner-settings)')?.getBoundingClientRect()
    const logo = zone.querySelector('.scanner-logo')?.getBoundingClientRect()
    const root = zone.getBoundingClientRect()
    return { root: [root.left, root.top, root.right, root.bottom], button: button && [button.left, button.top, button.right, button.bottom], logo: logo && [logo.left, logo.top, logo.right, logo.bottom] }
  })
  expect(uploadGeometry.button, JSON.stringify(uploadGeometry)).toBeTruthy()
  expect(uploadGeometry.button?.[0], JSON.stringify(uploadGeometry)).toBeGreaterThanOrEqual(0)
  expect(uploadGeometry.button?.[0], JSON.stringify(uploadGeometry)).toBeLessThan(1024)
  await expect(page.getByRole('button', { name: /上传文件/u })).toBeInViewport()
  await expect(page.locator('.scanner-logo')).toBeInViewport()
  await page.locator('.scanner-example').first().hover()
  const transform = await page.locator('.scanner-example-image img').first().evaluate((element) => getComputedStyle(element).transform)
  expect(transform).not.toBe('none')
  await expectNoScannerOverflow(page)
  await page.screenshot({ path: `${screenshotDirectory}/idle-1024.png`, fullPage: true })
  await page.getByRole('button', { name: '切换为浅色主题' }).click()
  await page.screenshot({ path: `${screenshotDirectory}/idle-light-1024.png`, fullPage: true })
  await page.getByRole('button', { name: '切换为深色主题' }).click()

  for (const viewport of [{ name: '768', width: 768, height: 820 }, { name: '480', width: 480, height: 820 }]) {
    await page.setViewportSize({ width: viewport.width, height: viewport.height })
    await page.locator('.scanner-start').evaluate((element) => element.scrollTo(0, 0))
    const mobileLogo = await page.locator('.scanner-logo').boundingBox()
    const mobileZone = await page.locator('.scanner-drop-zone').boundingBox()
    const mobileMain = await page.locator('.scanner-main').boundingBox()
    expect(mobileLogo?.y, JSON.stringify(mobileLogo)).toBeGreaterThanOrEqual(0)
    expect(mobileLogo?.y, JSON.stringify({ mobileLogo, mobileZone })).toBeGreaterThanOrEqual(mobileZone?.y ?? 0)
    expect(mobileZone?.y, JSON.stringify({ mobileZone, mobileMain })).toBeGreaterThanOrEqual(mobileMain?.y ?? 0)
    expect((mobileLogo?.y ?? 0) + (mobileLogo?.height ?? 0), JSON.stringify(mobileLogo)).toBeLessThanOrEqual(viewport.height)
    await expect(page.locator('.scanner-logo')).toBeInViewport()
    await expectNoScannerOverflow(page)
    await page.screenshot({ path: `${screenshotDirectory}/idle-${viewport.name}.png`, fullPage: true })
  }

  await page.setViewportSize({ width: 1024, height: 820 })
  const chooserPromise = page.waitForEvent('filechooser')
  await page.getByRole('button', { name: '上传解析', exact: true }).click()
  const chooser = await chooserPromise
  await chooser.setFiles({ name: '课堂笔记.txt', mimeType: 'text/plain', buffer: Buffer.from('课堂原始内容') })
  await expect(page.locator('.scanner-running')).toBeVisible()
  await expect(page.locator('.scanner-history-card .scanner-history-status')).toHaveText('解析中')
  await page.screenshot({ path: `${screenshotDirectory}/running-1024.png`, fullPage: true })
  await expect(page.locator('.scanner-result')).toBeVisible({ timeout: 8_000 })
  await expect(page.locator('.scanner-source-pane')).toContainText('原文件')
  await expect(page.getByRole('button', { name: 'OCR', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'No OCR', exact: true })).toBeVisible()
  await expectNoScannerOverflow(page)
  await page.screenshot({ path: `${screenshotDirectory}/result-1024.png`, fullPage: true })

  await page.getByRole('button', { name: 'No OCR', exact: true }).click()
  await expect(page.locator('.scanner-markdown-pane textarea').first()).toHaveValue(/No OCR/u)
  await page.setViewportSize({ width: 768, height: 820 })
  await expectNoScannerOverflow(page)
  await page.screenshot({ path: `${screenshotDirectory}/result-768.png`, fullPage: true })
  await page.setViewportSize({ width: 480, height: 820 })
  await expectNoScannerOverflow(page)
  await page.screenshot({ path: `${screenshotDirectory}/result-480.png`, fullPage: true })

  await page.setViewportSize({ width: 1024, height: 820 })
  await page.getByRole('button', { name: '我的', exact: true }).click()
  await page.getByRole('button', { name: '我的收藏', exact: true }).click()
  await expect(page.locator('.favorites-view')).toBeVisible()
  await page.getByRole('button', { name: /扫描器/u }).click()
  await expect(page.locator('.scanner-favorites-panel .scanner-history-card')).toHaveCount(1)
  await page.screenshot({ path: `${screenshotDirectory}/favorites-1024.png`, fullPage: true })
})
