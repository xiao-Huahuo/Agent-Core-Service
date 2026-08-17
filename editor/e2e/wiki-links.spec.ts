import { expect, test } from '@playwright/test'

const fileContent: Record<string, string> = {
  'notes/source.md': '# 来源\n\n[[target#目标章节|打开目标章节]]\n\n![[target#嵌入章节]]\n\n![[static/chart.png]]\n\n![[loop]]',
  'notes/target.md': '# 目标文档\n\n## 目标章节\n\n跳转后的正文。\n\n## 嵌入章节\n\n| 模型 | 成绩 |\n| --- | --- |\n| MetaWeave | 100 |',
  'notes/loop.md': '递归内容 ![[loop]]',
}

test('Obsidian wiki links suggest, navigate, highlight, and recursively embed', async ({ page }, testInfo) => {
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
      user_id: 'wiki-user', knowledge_dir: 'D:/Knowledge', active_library_id: 'default',
      knowledge_libraries: [{ library_id: 'default', name: 'Default', knowledge_dir: 'D:/Knowledge', is_active: true }],
    })
    if (url.pathname === '/knowledge/files/trash') return json({ entries: [] })
    if (url.pathname === '/knowledge/files') return json({
      tree: [{
        name: 'notes', path: 'notes', isDir: true, children: [
          { name: 'source.md', path: 'notes/source.md', isDir: false, size: 100 },
          { name: 'target.md', path: 'notes/target.md', isDir: false, size: 100 },
          { name: 'loop.md', path: 'notes/loop.md', isDir: false, size: 20 },
          { name: 'chart.png', path: 'notes/static/chart.png', isDir: false, size: 34 },
        ],
      }],
    })
    if (url.pathname === '/knowledge/files/content') return json({
      path, content: fileContent[path] ?? '', mtime: '2026-08-17 16:00', size: 100,
    })
    if (url.pathname === '/knowledge/files/raw') {
      return route.fulfill({
        status: 200,
        contentType: 'image/gif',
        body: Buffer.from('R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==', 'base64'),
      })
    }
    if (request.resourceType() === 'fetch' || request.resourceType() === 'xhr') return json({})
    await route.continue()
  })

  await page.addInitScript(() => localStorage.setItem('agent_editor_profile', JSON.stringify({
    userId: 'wiki-user', knowledgeDir: 'D:/Knowledge', activeLibraryId: 'default',
    knowledgeLibraries: [{ libraryId: 'default', name: 'Default', knowledgeDir: 'D:/Knowledge', isActive: true }],
  })))
  await page.goto('/')
  await page.getByRole('button', { name: 'Files' }).click()
  await page.getByText('source.md', { exact: true }).first().click()

  const editor = page.locator('.code-editor-input')
  await expect(editor).toHaveValue(fileContent['notes/source.md'])
  await editor.fill('[[tar')
  await expect(page.locator('.wiki-link-suggest')).toBeVisible()
  await expect(page.locator('.wiki-link-suggest')).toContainText('target')
  await expect(page.locator('.wiki-link-suggest')).toContainText('notes/')
  await expect(page.locator('.wiki-link-suggest footer')).toContainText('输入 # 链接标题')
  await page.keyboard.press('Escape')

  await editor.fill(fileContent['notes/source.md'])
  await editor.click({ button: 'right' })
  await page.getByRole('button', { name: '插入', exact: true }).hover()
  await expect(page.getByText('插入反向链接', { exact: true })).toBeVisible()
  await expect(page.getByText('插入嵌入链接', { exact: true })).toBeVisible()
  await page.keyboard.press('Escape')

  await page.getByRole('button', { name: 'Preview' }).click()
  await expect(page.locator('.wiki-link')).toHaveText('打开目标章节')
  await expect(page.locator('.wiki-embed table')).toContainText('MetaWeave')
  await expect(page.locator('.wiki-embed-image')).toBeVisible()
  await expect(page.locator('.wiki-embed-limit')).toContainText('5 层上限')
  await page.screenshot({ path: testInfo.outputPath('wiki-links-preview.png'), fullPage: true })

  await page.locator('.wiki-link').click()
  await expect(page.getByText('target.md', { exact: true }).last()).toBeVisible()
  await expect(page.locator('h2.wiki-anchor-highlight')).toHaveText('目标章节')
})
