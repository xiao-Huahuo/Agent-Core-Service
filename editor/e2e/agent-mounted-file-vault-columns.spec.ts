/*
 * Agent mounted-file and vault dynamic-column browser smoke tests.
 *
 * Usage:
 * Verifies the real workspace surfaces with mocked network data, including
 * encoded knowledge links, editor-sidebar navigation, and per-type vault columns.
 */
import { expect, test, type Page } from '@playwright/test'

const profile = {
  user_id: 'e2e-user',
  knowledge_dir: 'D:/Knowledge',
  active_library_id: 'default',
  knowledge_libraries: [{ library_id: 'default', name: 'Default', knowledge_dir: 'D:/Knowledge', is_active: true }],
}

const mountedFileName = '原神阴间地图汇总报告.md'
const mountedFilePath = `文档/${mountedFileName}`

async function mockWorkspace(page: Page): Promise<void> {
  let streamCompleted = false
  await page.route('**/*', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    if (url.pathname === '/agent/stream') {
      streamCompleted = true
      const event = {
        node: 'agent',
        content: `📄 [打开《${mountedFileName}》](/knowledge/files/raw?user_id=e2e-user&path=${encodeURIComponent(mountedFilePath)})`,
        tool_calls: [],
        trace: [],
        metadata: {
          citation_map: {
            K1: { source_uri: '资料/冬冬国.md', content: '测试来源' },
          },
          used_citations: ['K1'],
          change_snapshot: {
            snapshot_id: 'snap-e2e', session_id: 'e2e-session', run_id: 'run-e2e', created_at: '',
            additions: 10, deletions: 2, is_undone: false, edits: [],
            files: ['a.md', 'b.md', 'c.md', 'd.md'].map((path) => ({ path, additions: 2, deletions: 0, edits: [] })),
          },
        },
      }
      await route.fulfill({ status: 200, contentType: 'text/event-stream', body: `data: ${JSON.stringify(event)}\n\ndata: [DONE]\n\n` })
      return
    }
    if (url.pathname === '/agent/task-suggestions') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          suggestions: streamCompleted ? ['检查这次修改', '继续优化侧边栏', '解释本次改动'] : [],
        }),
      })
      return
    }
    if (url.pathname === '/health') {
      await route.fulfill({ status: 200, body: 'ok' })
      return
    }
    if (url.pathname === '/settings/profile') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(profile) })
      return
    }
    if (url.pathname === '/settings/models/status') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ embedding: 'ready', rerank: 'ready' }) })
      return
    }
    if (url.pathname === '/knowledge/files') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ tree: [{
          name: mountedFileName, path: mountedFilePath, isDir: false,
          size: 24576, createdAt: '2026-08-21 09:30', mtime: '2026-08-21 10:00',
          indexStatus: 'indexed', graphStatus: 'graphed',
        }] }),
      })
      return
    }
    if (url.pathname === '/vault/status') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ user_id: 'e2e-user', configured: true, item_count: 2 }) })
      return
    }
    if (url.pathname === '/vault/items') {
      const items = [
        {
          item_id: 'login-1', user_id: 'e2e-user', item_type: 'login', name: '工作账号',
          fields: { name: '工作账号', username: 'alice' }, safe_fields: { name: '工作账号', username: 'alice' },
          field_keys: ['name', 'username', 'password'], tags: [], deleted_at: '', created_at: '2026-08-21T09:00:00Z', updated_at: '2026-08-21T09:00:00Z',
        },
        {
          item_id: 'login-2', user_id: 'e2e-user', item_type: 'login', name: '私人账号',
          fields: { name: '私人账号', uri: 'https://example.com' }, safe_fields: { name: '私人账号', uri: 'https://example.com' },
          field_keys: ['name', 'password', 'uri'], tags: [], deleted_at: '', created_at: '2026-08-20T09:00:00Z', updated_at: '2026-08-20T09:00:00Z',
        },
      ]
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items, total: 2, type_counts: { login: 2, card: 0, identity: 0, secure_note: 0 } }) })
      return
    }
    if (url.pathname === '/vault/tags') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ tags: [] }) })
      return
    }
    if (url.pathname === '/sessions' && request.method() === 'POST') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ session_id: 'e2e-session', user_id: 'e2e-user', session_name: 'test', created_at: '', updated_at: '' }) })
      return
    }
    if (url.pathname === '/sessions') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
      return
    }
    if (url.pathname.endsWith('/messages')) {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
      return
    }
    if (url.pathname === '/favorites') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ favorites: [] }) })
      return
    }
    if (url.pathname === '/privacy') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ privacy: [] }) })
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
      userId: 'e2e-user', knowledgeDir: 'D:/Knowledge', activeLibraryId: 'default',
      knowledgeLibraries: [{ libraryId: 'default', name: 'Default', knowledgeDir: 'D:/Knowledge', isActive: true }],
    }))
    sessionStorage.setItem('metaweave_vault_token_e2e-user', JSON.stringify({ token: 'vault-token', expires_at: '2099-01-01T00:00:00Z' }))
  })
}

test('renders and opens an encoded Agent file block', async ({ page }, testInfo) => {
  await mockWorkspace(page)
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/')
  await page.evaluate(() => document.documentElement.setAttribute('data-theme', 'dark'))
  await page.getByRole('button', { name: 'Agent', exact: true }).click()
  await page.locator('textarea[placeholder="输入消息..."]').fill('挂载这个文件')
  await page.getByRole('button', { name: '发送' }).click()

  const block = page.locator('.agent-mounted-file')
  await expect(block).toBeVisible()
  await expect(block.locator('.agent-mounted-file__status')).toHaveCount(4)
  await expect(block).toContainText(`D:/Knowledge/${mountedFilePath}`)
  await page.screenshot({ path: testInfo.outputPath('agent-file-dark.png'), fullPage: true })

  await block.click()
  const editorSidebar = page.locator('.editor-sidebar-content')
  await expect(editorSidebar).toHaveAttribute('aria-hidden', 'false')
  await expect(editorSidebar).toBeVisible()
  await expect(editorSidebar.locator('.sidebar-editor-panel')).toBeVisible()
  await expect.poll(async () => (await editorSidebar.boundingBox())?.width ?? 0).toBeGreaterThan(300)
  await page.screenshot({ path: testInfo.outputPath('agent-file-sidebar-open.png'), fullPage: true })
})

test('keeps mounted files, changes, and input controls compact in Agent sidebar mode', async ({ page }, testInfo) => {
  await mockWorkspace(page)
  await page.setViewportSize({ width: 1180, height: 800 })
  await page.goto('/')
  await page.getByTitle('切换 Agent 面板').click()

  const agentColumn = page.locator('.agent-col')
  await expect(agentColumn).toHaveAttribute('aria-hidden', 'false')
  await agentColumn.locator('textarea[placeholder="输入消息..."]').fill('挂载这个文件')
  await agentColumn.getByRole('button', { name: '发送' }).click()

  const block = agentColumn.locator('.agent-mounted-file')
  await expect(block).toBeVisible()
  const mountedFileTitle = block.locator('.agent-mounted-file__name')
  await expect(mountedFileTitle).toHaveText(mountedFileName)
  const titleOverflow = await mountedFileTitle.evaluate((element) => {
    const style = getComputedStyle(element)
    return {
      display: style.display,
      overflow: style.overflow,
      textOverflow: style.textOverflow,
      whiteSpace: style.whiteSpace,
      isTruncated: element.scrollWidth > element.clientWidth,
    }
  })
  expect(titleOverflow).toEqual({
    display: 'block',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
    isTruncated: true,
  })
  await expect(block.locator('.agent-mounted-file__path')).toBeHidden()
  await expect(block.locator('.agent-mounted-file__created')).toBeHidden()
  await expect(block.locator('.agent-mounted-file__statuses')).toBeHidden()
  const blockGeometry = await block.evaluate((element) => {
    const bounds = element.getBoundingClientRect()
    const parent = element.parentElement?.getBoundingClientRect()
    return { width: bounds.width, parentWidth: parent?.width ?? 0, height: bounds.height }
  })
  expect(blockGeometry.width).toBeLessThanOrEqual(blockGeometry.parentWidth)
  expect(blockGeometry.height).toBeGreaterThanOrEqual(52)
  expect(blockGeometry.height).toBeLessThanOrEqual(58)

  const changeSummary = agentColumn.locator('.final-turn-summary.compact')
  await expect(changeSummary).toBeVisible()
  const panelSwitch = changeSummary.locator('.panel-switch')
  await expect(panelSwitch).toBeVisible()
  const switchAlignment = await changeSummary.evaluate((summary) => {
    const summaryBounds = summary.getBoundingClientRect()
    const switchBounds = (summary.querySelector('.panel-switch') as HTMLElement).getBoundingClientRect()
    return {
      rightGap: summaryBounds.right - switchBounds.right,
      switchCenter: (switchBounds.left + switchBounds.right) / 2,
      summaryCenter: (summaryBounds.left + summaryBounds.right) / 2,
    }
  })
  expect(switchAlignment.rightGap).toBeLessThanOrEqual(12)
  expect(switchAlignment.switchCenter).toBeGreaterThan(switchAlignment.summaryCenter)
  await expect(changeSummary.locator('.change-file-row')).toHaveCount(1)
  await expect(changeSummary).toContainText('再显示 3 个文件')

  const toolbar = agentColumn.locator('.input-toolbar')
  await expect(toolbar.getByRole('button', { name: '上传文件' })).toBeVisible()
  await expect(toolbar.getByRole('button', { name: '联网搜索' })).toBeVisible()
  await expect(toolbar.getByLabel('Agent 权限')).toBeVisible()
  await expect(toolbar.getByRole('button', { name: '配置模型' })).toBeVisible()
  await expect(toolbar.getByRole('button', { name: '发送' })).toBeVisible()
  const toolbarLayout = await toolbar.evaluate((element) => {
    const visibleControls = Array.from(element.querySelectorAll<HTMLElement>('button, summary, .context-progress'))
      .filter((item) => getComputedStyle(item).display !== 'none')
      .map((item) => {
        const rect = item.getBoundingClientRect()
        return { left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom }
      })
    const overlaps = visibleControls.some((current, index) => visibleControls.slice(index + 1).some((next) => (
      current.left < next.right && current.right > next.left && current.top < next.bottom && current.bottom > next.top
    )))
    return { overlaps, scrollWidth: element.scrollWidth, clientWidth: element.clientWidth }
  })
  expect(toolbarLayout.overlaps).toBe(false)
  expect(toolbarLayout.scrollWidth).toBeLessThanOrEqual(toolbarLayout.clientWidth)

  const suggestions = agentColumn.locator('.task-suggestions')
  await expect(suggestions.locator('.suggestion-button')).toHaveCount(3)
  await expect(agentColumn.locator('.chat-input-wrap .suggestion-button')).toHaveCount(0)
  const contentOrder = await agentColumn.locator('.bubble-row.assistant, .final-turn-summary, .task-suggestions').evaluateAll((elements) => (
    elements.map((element) => element.className)
  ))
  expect(contentOrder.at(-1)).toContain('task-suggestions')

  const stacking = await agentColumn.evaluate((element) => {
    const messages = element.querySelector('.message-list') as HTMLElement
    const welcome = element.querySelector('.welcome-center') as HTMLElement | null
    return {
      messages: Number(getComputedStyle(messages).zIndex),
      welcome: welcome ? Number(getComputedStyle(welcome).zIndex) : 0,
    }
  })
  expect(stacking.messages).toBeGreaterThan(stacking.welcome)

  await page.screenshot({ path: testInfo.outputPath('agent-sidebar-compact.png'), fullPage: true })

  await block.click()
  await expect(page.locator('.editor-sidebar-content')).toHaveAttribute('aria-hidden', 'true')
  await expect(page.locator('.main-shell .editor-panel .tab-title')).toHaveText(mountedFileName)
})

test('reveals all asynchronous follow-up suggestions below the Agent output', async ({ page }, testInfo) => {
  await mockWorkspace(page)
  await page.setViewportSize({ width: 1100, height: 420 })
  await page.goto('/')
  await page.getByRole('button', { name: 'Agent', exact: true }).click()
  await page.locator('textarea[placeholder="输入消息..."]').fill('挂载这个文件')
  await page.getByRole('button', { name: '发送' }).click()

  const messageList = page.locator('.agent-page-mode .message-list')
  const suggestions = messageList.locator('.task-suggestions')
  await expect(suggestions.locator('.suggestion-button')).toHaveCount(3)
  const visibility = await messageList.evaluate((list) => {
    const listBounds = list.getBoundingClientRect()
    const suggestionElement = list.querySelector('.task-suggestions') as HTMLElement
    const suggestionBounds = suggestionElement.getBoundingClientRect()
    return {
      height: suggestionBounds.height,
      borderTopWidth: getComputedStyle(suggestionElement).borderTopWidth,
      topVisible: suggestionBounds.top >= listBounds.top,
      bottomVisible: suggestionBounds.bottom <= listBounds.bottom + 1,
    }
  })
  expect(visibility.height).toBeGreaterThanOrEqual(26)
  expect(visibility.borderTopWidth).toBe('0px')
  expect(visibility.topVisible).toBe(true)
  expect(visibility.bottomVisible).toBe(true)

  await page.screenshot({ path: testInfo.outputPath('agent-follow-up-suggestions-visible.png'), fullPage: true })
})

test('shows the selected vault type non-empty field union', async ({ page }, testInfo) => {
  await mockWorkspace(page)
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/')
  await page.getByRole('button', { name: '库', exact: true }).click()
  const vaultButton = page.locator('button[aria-label="密码库"]')
  await expect(vaultButton).toBeVisible()
  await vaultButton.click({ force: true })
  await page.getByRole('button', { name: /登录/ }).click()

  await expect(page.locator('.vault-table th')).toHaveText(['', '项目名称', '用户名', '密码', '网站 URI', '创建时间', '拥有者'])
  await expect(page.locator('.vault-table')).not.toContainText('secret')
  await page.screenshot({ path: testInfo.outputPath('vault-login-columns.png'), fullPage: true })
})
