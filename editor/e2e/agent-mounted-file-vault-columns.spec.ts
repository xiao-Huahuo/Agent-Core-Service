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

async function mockWorkspace(page: Page): Promise<void> {
  await page.route('**/*', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    if (url.pathname === '/agent/stream') {
      const event = {
        node: 'agent',
        content: '📄 [打开《简单word.docx》](/knowledge/files/raw?user_id=e2e-user&path=%E6%96%87%E6%A1%A3%2F%E7%AE%80%E5%8D%95word.docx)',
        tool_calls: [],
        trace: [],
      }
      await route.fulfill({ status: 200, contentType: 'text/event-stream', body: `data: ${JSON.stringify(event)}\n\ndata: [DONE]\n\n` })
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
          name: '简单word.docx', path: '文档/简单word.docx', isDir: false,
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
  await expect(block).toContainText('D:/Knowledge/文档/简单word.docx')
  await page.screenshot({ path: testInfo.outputPath('agent-file-dark.png'), fullPage: true })

  await block.click()
  const editorSidebar = page.locator('.editor-sidebar-content')
  await expect(editorSidebar).toHaveAttribute('aria-hidden', 'false')
  await expect(editorSidebar).toBeVisible()
  await expect(editorSidebar.locator('.sidebar-editor-panel')).toBeVisible()
  await expect.poll(async () => (await editorSidebar.boundingBox())?.width ?? 0).toBeGreaterThan(300)
  await page.screenshot({ path: testInfo.outputPath('agent-file-sidebar-open.png'), fullPage: true })
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
