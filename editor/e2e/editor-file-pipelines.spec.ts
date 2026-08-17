import { expect, test, type Page } from '@playwright/test'

const files = [
  'note.md', 'note.txt', 'data.csv', 'legacy.xls', 'sheet.xlsx', 'report.docx',
  'scan.pdf', 'slides.pptx', 'photo.png', 'script.py', 'legacy.doc', 'README.weird',
]

async function openFile(page: Page, name: string, modes: string[]) {
  await page.getByText(name, { exact: true }).first().click()
  await expect(page.locator('.editor-mode-switch button')).toHaveText(modes)
  await expect(page.locator('.editor-mode-switch svg.ic-icon')).toHaveCount(modes.length)
  expect(await page.locator('.editor-mode-switch svg.ic-icon').evaluateAll(
    (icons) => icons.every((icon) => icon.childElementCount > 0),
  )).toBe(true)
}

test('editor uses the complete modality-specific surface pipeline', async ({ page }) => {
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
      user_id: 'e2e-user', knowledge_dir: 'D:/Knowledge', active_library_id: 'default',
      knowledge_libraries: [{ library_id: 'default', name: 'Default', knowledge_dir: 'D:/Knowledge', is_active: true }],
    })
    if (url.pathname === '/knowledge/files/trash') return json({ entries: [] })
    if (url.pathname === '/knowledge/files') return json({
      tree: files.map((name) => ({ name, path: name, isDir: false, mtime: '2026-08-17 11:00', size: 10 })),
    })
    if (url.pathname === '/knowledge/files/content') return json({
      path, content: path === 'note.md' ? '# Markdown body' : `${path} raw text`, mtime: '2026-08-17 11:00', size: 10,
    })
    if (url.pathname === '/knowledge/files/preview') {
      const base = { path, mtime: '2026-08-17 11:00', size: 10, extension: `.${path.split('.').pop()}` }
      if (path === 'data.csv') return json({ ...base, kind: 'table', content: 'a,b\n1,2\n', sheets: [{ name: 'data', rows: [['a', 'b'], ['1', '2']] }], readonly: false })
      if (path.endsWith('.xls') || path.endsWith('.xlsx')) return json({ ...base, kind: 'table', sheets: [{ name: 'Sheet1', rows: [['A', 'B']] }], readonly: true })
      if (path === 'report.docx') return json({ ...base, kind: 'document', html: '<p>DOCX</p><img alt="embedded" src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==">', semantic_markdown: '# DOCX projection', readonly: true })
      if (path === 'scan.pdf') return json({ ...base, kind: 'pdf', data_url: 'data:application/pdf;base64,JVBERi0xLjQ=', semantic_markdown: '# PDF projection', readonly: true })
      if (path === 'slides.pptx') return json({ ...base, kind: 'presentation', semantic_markdown: '# PPTX projection', readonly: true })
      if (path === 'photo.png') return json({ ...base, kind: 'image', data_url: 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==', semantic_markdown: '# Image projection', readonly: true })
      if (path === 'README.weird') return json({ ...base, kind: 'text', content: 'plain fallback', readonly: false })
      return json({ ...base, kind: 'unsupported', message: '当前文件类型暂不支持预览。', readonly: true })
    }
    if (request.resourceType() === 'fetch' || request.resourceType() === 'xhr') return json({})
    await route.continue()
  })

  await page.addInitScript(() => localStorage.setItem('agent_editor_profile', JSON.stringify({
    userId: 'e2e-user', knowledgeDir: 'D:/Knowledge', activeLibraryId: 'default',
    knowledgeLibraries: [{ libraryId: 'default', name: 'Default', knowledgeDir: 'D:/Knowledge', isActive: true }],
  })))
  await page.goto('/')
  await page.getByRole('button', { name: 'Files' }).click()

  await openFile(page, 'note.md', ['Edit', 'Preview', 'Split'])
  await expect(page.locator('.code-editor')).toBeVisible()
  await page.getByRole('button', { name: 'Preview' }).click()
  await expect(page.locator('.markdown-preview')).toBeVisible()
  await page.getByRole('button', { name: 'Split' }).click()
  await expect(page.locator('.code-editor')).toBeVisible()
  await expect(page.locator('.markdown-preview')).toBeVisible()
  await openFile(page, 'note.txt', ['Text'])
  await expect(page.locator('.code-editor')).toBeVisible()
  await openFile(page, 'script.py', ['Code'])
  await expect(page.locator('.code-editor')).toBeVisible()
  await openFile(page, 'data.csv', ['Text', 'Forms'])
  await expect(page.locator('.code-editor')).toBeVisible()
  await page.getByRole('button', { name: 'Forms' }).click()
  await expect(page.locator('.table-preview')).toContainText('1')
  await openFile(page, 'legacy.xls', ['Forms'])
  await expect(page.locator('.table-preview')).toContainText('A')
  await openFile(page, 'sheet.xlsx', ['Forms'])
  await expect(page.locator('.table-preview')).toContainText('A')
  await openFile(page, 'report.docx', ['Preview', 'Markdown'])
  await expect(page.locator('.document-preview img[alt="embedded"]')).toBeVisible()
  await page.getByRole('button', { name: 'Markdown' }).click()
  await expect(page.locator('.code-preview')).toContainText('DOCX projection')
  await openFile(page, 'scan.pdf', ['Preview', 'Markdown'])
  await expect(page.locator('iframe.pdf-preview')).toBeVisible()
  await page.getByRole('button', { name: 'Markdown' }).click()
  await expect(page.locator('.code-preview')).toContainText('PDF projection')
  await openFile(page, 'slides.pptx', ['Preview', 'Markdown'])
  await expect(page.locator('.presentation-preview')).toBeVisible()
  await page.getByRole('button', { name: 'Markdown' }).click()
  await expect(page.locator('.code-preview')).toContainText('PPTX projection')
  await openFile(page, 'photo.png', ['Preview', 'Markdown'])
  await expect(page.locator('.multimodal-preview')).toBeVisible()
  await page.getByRole('button', { name: 'Markdown' }).click()
  await expect(page.locator('.code-preview')).toContainText('Image projection')
  await openFile(page, 'legacy.doc', ['Binary'])
  await expect(page.locator('.preview-message')).toContainText('不支持预览')
  await openFile(page, 'README.weird', ['Text'])
  await expect(page.locator('.code-editor')).toBeVisible()
})
