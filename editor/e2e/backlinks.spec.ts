import { expect, test } from '@playwright/test'

const documents: Record<string, string> = {
  'notes/source.md': '整篇 [[target]]\n标题 [[target#目标章节|打开目标章节]]',
  'notes/target.md': '# 目标文档\n\n## 目标章节\n\n正文',
}

test('shows persisted incoming links in the Markdown bottom panel', async ({ page }, testInfo) => {
  let savedShowBacklinks = false
  await page.route('**/*', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.searchParams.get('path') ?? ''
    const json = (body: unknown) => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(body),
    })
    if (url.pathname === '/health') return route.fulfill({ status: 200, body: 'ok' })
    if (url.pathname === '/settings/models/status') return json({ embedding: 'ready', rerank: 'ready' })
    if (url.pathname === '/settings/profile') return json({
      user_id: 'backlink-user', knowledge_dir: 'D:/Knowledge', active_library_id: 'default', show_backlinks: false,
      knowledge_libraries: [{ library_id: 'default', name: 'Default', knowledge_dir: 'D:/Knowledge', is_active: true }],
    })
    if (url.pathname === '/settings/appearance/config') {
      savedShowBacklinks = Boolean((request.postDataJSON() as { show_backlinks?: boolean }).show_backlinks)
      return json({
        user_id: 'backlink-user', theme_primary_color: '', theme_soft_color: '',
        show_backlinks: savedShowBacklinks, updated_at: '2026-08-20T00:00:00Z',
      })
    }
    if (url.pathname === '/knowledge/files/trash') return json({ entries: [] })
    if (url.pathname === '/knowledge/files') return json({
      tree: [{
        name: 'notes', path: 'notes', isDir: true, children: [
          { name: 'source.md', path: 'notes/source.md', isDir: false, size: 80 },
          { name: 'target.md', path: 'notes/target.md', isDir: false, size: 80 },
        ],
      }],
    })
    if (url.pathname === '/knowledge/files/content') return json({
      path, content: documents[path] ?? '', mtime: '2026-08-20 00:00', size: 80,
    })
    if (request.resourceType() === 'fetch' || request.resourceType() === 'xhr') return json({})
    await route.continue()
  })

  await page.addInitScript(() => localStorage.setItem('agent_editor_profile', JSON.stringify({
    userId: 'backlink-user', knowledgeDir: 'D:/Knowledge', activeLibraryId: 'default',
    knowledgeLibraries: [{ libraryId: 'default', name: 'Default', knowledgeDir: 'D:/Knowledge', isActive: true }],
  })))
  await page.goto('/')
  await page.getByRole('button', { name: 'Files' }).click()
  await page.getByRole('button', { name: 'target.md 收藏' }).evaluate((element) => (element as HTMLElement).click())
  await expect(page.locator('.code-editor-input')).toHaveValue(documents['notes/target.md'])

  await page.locator('.code-editor-input').click({ button: 'right' })
  await page.getByText('显示反向链接', { exact: true }).click()

  await expect(page.locator('.backlinks-panel')).toBeVisible()
  await expect(page.locator('.backlink-entry')).toContainText('source.md')
  await expect(page.locator('.backlink-token-row').filter({ hasText: '[[target]]' }).locator('.backlink-target-kind')).toHaveText('文章')
  const headingLink = page.locator('.backlink-token-row').filter({ hasText: '[[target#目标章节|打开目标章节]]' })
  await expect(headingLink.locator('code')).toHaveText('[[target#目标章节|打开目标章节]]')
  await expect(headingLink.locator('.backlink-target-kind')).toHaveText('标题 · 目标章节')
  expect(savedShowBacklinks).toBe(true)
  await page.screenshot({ path: testInfo.outputPath('backlinks-panel.png'), fullPage: true })

  await page.getByRole('button', { name: 'Settings' }).click()
  await page.getByRole('button', { name: '外观' }).click()
  await expect(page.locator('#show-backlinks-setting')).toBeChecked()
})
