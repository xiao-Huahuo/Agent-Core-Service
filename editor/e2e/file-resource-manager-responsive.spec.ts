/*
 * File resource-manager container-responsive browser smoke test.
 *
 * Usage:
 * Opens the browser sidebar and drags its left edge while the viewport stays
 * fixed, proving that the workspace card itself drives desktop, tablet, and
 * mobile resource-manager layouts. The three screenshots are acceptance
 * evidence for the user-visible responsive behavior.
 */
import { expect, test, type Page } from '@playwright/test'

const screenshotDirectory = '../docs/screenshots/file-resource-manager'

/** Supplies stable resource data without depending on a running backend. */
async function mockFileWorkspace(page: Page): Promise<void> {
  const files = [
    { name: '研究资料', path: '研究资料', isDir: true, size: 0, mtime: '2026-08-24 12:00', indexStatus: 'clean', graphStatus: 'graphed' },
    { name: '三级响应式布局验收记录.md', path: '三级响应式布局验收记录.md', isDir: false, size: 18642, mtime: '2026-08-24 11:42', ingestedAt: '2026-08-24 11:50', indexStatus: 'indexed', graphStatus: 'graphed' },
    { name: '侧边栏拖动测试数据.csv', path: '侧边栏拖动测试数据.csv', isDir: false, size: 8240, mtime: '2026-08-23 18:25', ingestedAt: '2026-08-23 18:30', indexStatus: 'indexed', graphStatus: 'dirty' },
    { name: '工作区宽度对照截图.png', path: '工作区宽度对照截图.png', isDir: false, size: 248320, mtime: '2026-08-22 09:10', ingestedAt: '2026-08-22 09:14', indexStatus: 'dirty', graphStatus: 'dirty' },
  ]

  await page.route('**/*', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const json = (body: unknown) => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(body),
    })

    if (url.pathname === '/health') {
      await route.fulfill({ status: 200, contentType: 'text/plain', body: 'ok' })
      return
    }
    if (url.pathname === '/settings/models/status') {
      await json({ embedding: 'ready', rerank: 'ready' })
      return
    }
    if (url.pathname === '/settings/profile') {
      await json({
        user_id: 'responsive-smoke',
        knowledge_dir: 'D:/Knowledge',
        active_library_id: 'default',
        knowledge_libraries: [{ library_id: 'default', name: '响应式验收库', knowledge_dir: 'D:/Knowledge', is_active: true }],
      })
      return
    }
    if (url.pathname === '/knowledge/files') {
      await json({ tree: files })
      return
    }
    if (url.pathname === '/knowledge/files/events') {
      await route.fulfill({ status: 200, contentType: 'text/event-stream', body: ': responsive smoke\n\n' })
      return
    }
    if (url.pathname === '/favorites') {
      await json({ favorites: [] })
      return
    }
    if (url.pathname === '/privacy') {
      await json({ privacy: [] })
      return
    }
    if (url.pathname === '/knowledge/trash') {
      await json({ entries: [] })
      return
    }
    if (url.pathname === '/sessions' && request.method() === 'GET') {
      await json([])
      return
    }
    if (url.pathname === '/git/status') {
      await json({
        initialized: false,
        repository_root: '',
        current_branch: '',
        upstream: '',
        ahead: 0,
        behind: 0,
        detached: false,
        branches: [],
        remote_branches: [],
        remotes: [],
        changes: [],
        untracked: [],
        ignored: [],
        has_changes: false,
      })
      return
    }
    if (request.resourceType() === 'fetch' || request.resourceType() === 'xhr') {
      await json({})
      return
    }
    await route.continue()
  })

  await page.addInitScript(() => {
    localStorage.setItem('agent_editor_profile', JSON.stringify({
      userId: 'responsive-smoke',
      knowledgeDir: 'D:/Knowledge',
      activeLibraryId: 'default',
      knowledgeLibraries: [{ libraryId: 'default', name: '响应式验收库', knowledgeDir: 'D:/Knowledge', isActive: true }],
    }))
  })
}

/** Selects the page under test without coupling this layout smoke to the animated navigation menu. */
async function openResourceManager(page: Page): Promise<void> {
  await page.evaluate(() => {
    type WorkspaceStore = { mainView: string; setMainView: (view: string) => void }
    type PiniaRoot = { _s: Map<string, WorkspaceStore> }
    const app = (document.querySelector('#app') as HTMLElement & {
      __vue_app__?: { _context: { provides: Record<PropertyKey, unknown> } }
    }).__vue_app__
    const pinia = app && Reflect.ownKeys(app._context.provides)
      .map((key) => app._context.provides[key])
      .find((value): value is PiniaRoot => Boolean(value && typeof value === 'object' && '_s' in value))
    const workspace = pinia?._s.get('workspace')
    if (!workspace) {
      throw new Error(`Workspace Pinia store is unavailable: app=${Boolean(app)}, stores=${JSON.stringify(pinia ? [...pinia._s.keys()] : [])}`)
    }
    workspace.setMainView('resources')
    if (workspace.mainView !== 'resources') throw new Error(`Workspace main view stayed at ${workspace.mainView}.`)
  })
}

/** Matches the regular resource-page shell by closing unrelated side panels through their real controls. */
async function closePeripheralSidebars(page: Page): Promise<void> {
  const fileSidebar = page.locator('.file-col')
  if (await fileSidebar.getAttribute('aria-hidden') === 'false') {
    await page.getByRole('button', { name: 'Files', exact: true }).click()
  }
  const agentSidebar = page.locator('.agent-col')
  if (await agentSidebar.getAttribute('aria-hidden') === 'false') {
    await page.getByTitle('切换 Agent 面板').click()
  }
}

/** Drags the browser's left edge until the main workspace card reaches a target width. */
async function resizeMainCard(page: Page, targetWidth: number): Promise<number> {
  const mainCard = page.locator('.main-shell.ide-panel')
  const browserResizer = page.getByRole('separator', { name: 'Resize browser sidebar' })
  const [cardBox, handleBox] = await Promise.all([mainCard.boundingBox(), browserResizer.boundingBox()])
  if (!cardBox || !handleBox) throw new Error('Workspace resize geometry is unavailable.')

  const handleX = handleBox.x + handleBox.width / 2
  const handleY = handleBox.y + handleBox.height / 2
  await page.mouse.move(handleX, handleY)
  await page.mouse.down()
  await expect(page.locator('.workspace-page')).toHaveClass(/resizing-column/)
  await page.mouse.move(handleX + targetWidth - cardBox.width, handleY, { steps: 8 })
  await page.waitForTimeout(32)
  await page.mouse.up()
  await expect.poll(async () => (await mainCard.boundingBox())?.width ?? 0).toBeGreaterThan(targetWidth - 18)
  await expect.poll(async () => (await mainCard.boundingBox())?.width ?? 0).toBeLessThan(targetWidth + 18)
  return (await mainCard.boundingBox())?.width ?? 0
}

/** Returns geometry signals that fail on clipping, horizontal overflow, or overlap. */
async function resourceGeometry(page: Page) {
  return page.locator('.resource-manager').evaluate((manager) => {
    const toolbar = manager.querySelector<HTMLElement>('.resource-toolbar')
    const content = manager.querySelector<HTMLElement>('.content-shell')
    const rows = Array.from(manager.querySelectorAll<HTMLElement>('.resource-row'))
    const managerBox = manager.getBoundingClientRect()
    const toolbarBox = toolbar?.getBoundingClientRect()
    const contentBox = content?.getBoundingClientRect()
    const visibleToolbarControls = Array.from(manager.querySelectorAll<HTMLElement>('.resource-toolbar button'))
      .filter((element) => getComputedStyle(element).display !== 'none')
      .map((element) => element.getBoundingClientRect())
    const controlsOverlap = visibleToolbarControls.some((current, index) => (
      visibleToolbarControls.slice(index + 1).some((next) => (
        current.left < next.right && current.right > next.left
        && current.top < next.bottom && current.bottom > next.top
      ))
    ))
    return {
      managerWidth: managerBox.width,
      managerOverflow: manager.scrollWidth - manager.clientWidth,
      toolbarOverflow: (toolbar?.scrollWidth ?? 0) - (toolbar?.clientWidth ?? 0),
      contentOverflow: (content?.scrollWidth ?? 0) - (content?.clientWidth ?? 0),
      toolbarInside: Boolean(toolbarBox && toolbarBox.left >= managerBox.left && toolbarBox.right <= managerBox.right + 1),
      contentInside: Boolean(contentBox && contentBox.left >= managerBox.left && contentBox.right <= managerBox.right + 1),
      controlsOverlap,
      rowHeights: rows.map((row) => Math.round(row.getBoundingClientRect().height)),
    }
  })
}

test('responds to three workspace-card widths while the browser sidebar is dragged', async ({ page }) => {
  test.setTimeout(60_000)
  const pageErrors: string[] = []
  const consoleErrors: string[] = []
  page.on('pageerror', (error) => pageErrors.push(error.message))
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text())
  })
  await mockFileWorkspace(page)
  await page.setViewportSize({ width: 1720, height: 920 })
  await page.goto('/')
  await expect(page.locator('.workspace-page')).toBeVisible()
  await openResourceManager(page)
  await closePeripheralSidebars(page)
  await page.waitForTimeout(250)
  expect(pageErrors).toEqual([])
  expect(consoleErrors).toEqual([])
  await expect(page.locator('.resource-manager')).toBeVisible()
  await expect(page.locator('.resource-row')).toHaveCount(4)
  await page.getByRole('button', { name: '打开或收起右侧浏览器' }).click()
  await expect(page.locator('.browser-sidebar-content')).toBeVisible()

  const widths = [
    { name: 'desktop', target: 1120, minimum: 1041, maximum: 1300 },
    { name: 'tablet', target: 780, minimum: 641, maximum: 1040 },
    { name: 'mobile', target: 480, minimum: 320, maximum: 640 },
  ] as const

  for (const width of widths) {
    const actualWidth = await resizeMainCard(page, width.target)
    expect(actualWidth).toBeGreaterThanOrEqual(width.minimum)
    expect(actualWidth).toBeLessThanOrEqual(width.maximum)
    const geometry = await resourceGeometry(page)
    expect(geometry.managerOverflow).toBeLessThanOrEqual(1)
    expect(geometry.toolbarOverflow).toBeLessThanOrEqual(1)
    expect(geometry.contentOverflow).toBeLessThanOrEqual(1)
    expect(geometry.toolbarInside).toBe(true)
    expect(geometry.contentInside).toBe(true)
    expect(geometry.controlsOverlap).toBe(false)
    if (width.name === 'desktop') expect(Math.max(...geometry.rowHeights)).toBeLessThanOrEqual(40)
    if (width.name === 'mobile') expect(Math.min(...geometry.rowHeights)).toBeGreaterThanOrEqual(58)
    await page.screenshot({ path: `${screenshotDirectory}/${width.name}.png`, fullPage: true })
  }
})
