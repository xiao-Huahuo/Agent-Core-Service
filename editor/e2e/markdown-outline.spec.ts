/*
 * Markdown outline browser smoke test.
 *
 * Exercises the real editor workspace with routed backend fixtures, including
 * toolbar motion, tree controls, search emphasis, caret tracking, and scroll.
 */
import { expect, test } from '@playwright/test'

const markdown = [
  '# Guide',
  'Introduction',
  '## Setup',
  ...Array.from({ length: 45 }, (_, index) => `setup line ${index + 1}\n`),
  '### Install on Windows',
  ...Array.from({ length: 45 }, (_, index) => `install line ${index + 1}\n`),
  '## Usage',
  'Done',
].join('\n')

test('Markdown outline works inside the editor card', async ({ page }, testInfo) => {
  await page.route('**/*', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const json = (body: unknown) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
    if (url.pathname === '/health') return route.fulfill({ status: 200, body: 'ok' })
    if (url.pathname === '/settings/models/status') return json({ embedding: 'ready', rerank: 'ready' })
    if (url.pathname === '/settings/profile') return json({
      user_id: 'outline-user', knowledge_dir: 'D:/Knowledge', active_library_id: 'default',
      knowledge_libraries: [{ library_id: 'default', name: 'Default', knowledge_dir: 'D:/Knowledge', is_active: true }],
    })
    if (url.pathname === '/knowledge/files/trash') return json({ entries: [] })
    if (url.pathname === '/favorites') return json({ favorites: [] })
    if (url.pathname === '/privacy') return json({ privacy: [] })
    if (url.pathname === '/knowledge/files') return json({
      tree: [{ name: 'outline.md', path: 'outline.md', isDir: false, mtime: '2026-08-23 22:00', size: markdown.length }],
    })
    if (url.pathname === '/knowledge/files/content') return json({
      path: 'outline.md', content: markdown, mtime: '2026-08-23 22:00', size: markdown.length,
    })
    if (request.resourceType() === 'fetch' || request.resourceType() === 'xhr') return json({})
    await route.continue()
  })

  await page.addInitScript(() => localStorage.setItem('agent_editor_profile', JSON.stringify({
    userId: 'outline-user', knowledgeDir: 'D:/Knowledge', activeLibraryId: 'default',
    knowledgeLibraries: [{ libraryId: 'default', name: 'Default', knowledgeDir: 'D:/Knowledge', isActive: true }],
  })))
  await page.addInitScript(() => localStorage.setItem('agent_editor_theme_mode', 'light'))
  await page.goto('/')
  await page.getByRole('button', { name: 'Files' }).click()
  await page.getByText('outline.md', { exact: true }).first().click()

  const outline = page.locator('.markdown-outline')
  const outlineButton = page.getByRole('button', { name: '目录树' })
  const saveButton = page.getByRole('button', { name: 'Save' })
  await expect(outlineButton).toBeVisible()
  await expect(outline).toHaveAttribute('aria-hidden', 'true')
  await outlineButton.click()
  await expect(outline).toHaveClass(/open/u)
  await expect(outline.locator('.outline-toolbar')).toHaveCSS('border-bottom-style', 'none')
  await expect(outline.locator('.outline-header-action').first()).toHaveCSS('height', '28px')
  await expect(outline.locator('.outline-header-action').first()).toHaveCSS('border-style', 'none')
  await expect(outline.locator('.outline-search')).toHaveCSS('border-radius', '999px')
  await expect(outline).toHaveCSS('border-left-style', 'solid')
  await expect.poll(async () => outline.evaluate((element) => getComputedStyle(element).transform)).toBe('matrix(1, 0, 0, 1, 0, 0)')

  await expect(outline.locator('.tree-item')).toHaveCount(4)
  await expect(outline.locator('.tree-label')).toHaveCount(2)
  await expect(outline.locator('.file-item')).toHaveCount(2)
  const rootToggle = outline.locator('.tree-toggle').first()
  const rootChildren = outline.locator('.tree-children-wrapper').first()
  await expect(rootChildren).toHaveCSS('transition-duration', '0.3s')
  await outline.getByRole('button', { name: '全部折叠' }).click()
  await expect(rootToggle).not.toBeChecked()
  await expect.poll(() => rootChildren.evaluate((element) => element.getBoundingClientRect().height)).toBe(0)
  await outline.getByRole('button', { name: '全部展开' }).click()
  await expect(rootToggle).toBeChecked()
  await expect.poll(() => rootChildren.evaluate((element) => element.getBoundingClientRect().height)).toBeGreaterThan(0)

  await outline.getByRole('searchbox', { name: '搜索标题' }).fill('install')
  await expect(outline.locator('.tree-name strong')).toHaveText('Install')
  await outline.getByRole('searchbox', { name: '搜索标题' }).fill('')

  const textarea = page.locator('.code-editor-input')
  const setupOffset = markdown.indexOf('## Setup')
  await textarea.evaluate((element, offset) => {
    const input = element as HTMLTextAreaElement
    input.focus()
    input.setSelectionRange(offset, offset)
    input.dispatchEvent(new Event('select', { bubbles: true }))
  }, setupOffset)
  await expect(outline.locator('.is-selected')).toContainText('Setup')

  await outline.getByText('Install on Windows', { exact: true }).click()
  await expect.poll(() => textarea.evaluate((element) => (element as HTMLTextAreaElement).selectionStart)).toBe(markdown.indexOf('### Install'))
  await expect.poll(() => textarea.evaluate((element) => element.scrollTop)).toBeGreaterThan(1_000)

  await saveButton.hover()
  await expect.poll(() => saveButton.locator('.save-motion-icon').evaluate((element) => getComputedStyle(element).transform)).not.toBe('none')
  const box = await saveButton.boundingBox()
  expect(box).not.toBeNull()
  await page.mouse.move(box!.x + box!.width / 2, box!.y + box!.height / 2)
  await page.mouse.down()
  expect(await saveButton.evaluate((element) => getComputedStyle(element).transform)).not.toBe('none')
  await page.mouse.up()

  const screenshotPath = process.env.MARKDOWN_OUTLINE_SCREENSHOT ?? testInfo.outputPath('markdown-outline.png')
  await page.screenshot({ path: screenshotPath, fullPage: true })

  await page.getByRole('button', { name: 'Preview' }).click()
  await expect(outline).toHaveClass(/open/u)
  await outline.getByText('Usage', { exact: true }).click()
  await expect(outline.locator('.is-selected')).toContainText('Usage')
  await page.getByRole('button', { name: 'Split' }).click()
  await expect(page.locator('.code-editor')).toBeVisible()
  await expect(page.locator('.markdown-preview')).toBeVisible()
  await page.getByRole('button', { name: 'Edit' }).click()
  await expect.poll(() => textarea.evaluate((element) => (element as HTMLTextAreaElement).selectionStart)).toBe(markdown.indexOf('## Usage'))
  await expect(outline.locator('.is-selected')).toContainText('Usage')
})
