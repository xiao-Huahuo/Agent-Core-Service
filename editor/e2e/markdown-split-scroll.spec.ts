/**
 * Markdown Split bidirectional scroll synchronization regression.
 *
 * Usage:
 * Opens a long real Markdown document and verifies both panes traverse their
 * complete independent scroll ranges at matching normalized positions.
 */
import { expect, test, type Locator } from '@playwright/test'

const markdown = Array.from({ length: 90 }, (_, index) => (
  `## Section ${index + 1}\n\nParagraph ${index + 1} with enough text to render a stable preview block.\n`
)).join('\n')

async function setScrollRatio(locator: Locator, ratio: number): Promise<void> {
  await locator.evaluate((element, value) => {
    const maxScrollTop = Math.max(0, element.scrollHeight - element.clientHeight)
    element.scrollTop = maxScrollTop * value
    element.dispatchEvent(new Event('scroll', { bubbles: true }))
  }, ratio)
}

async function readScrollRatio(locator: Locator): Promise<number> {
  return locator.evaluate((element) => {
    const maxScrollTop = Math.max(0, element.scrollHeight - element.clientHeight)
    return maxScrollTop > 0 ? element.scrollTop / maxScrollTop : 0
  })
}

test('Split panes reach matching middle and bottom positions in both directions', async ({ page }, testInfo) => {
  await page.route('**/*', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const json = (body: unknown) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
    if (url.pathname === '/health') return route.fulfill({ status: 200, body: 'ok' })
    if (url.pathname === '/settings/models/status') return json({ embedding: 'ready', rerank: 'ready' })
    if (url.pathname === '/settings/profile') return json({
      user_id: 'split-user', knowledge_dir: 'D:/Knowledge', active_library_id: 'default',
      knowledge_libraries: [{ library_id: 'default', name: 'Default', knowledge_dir: 'D:/Knowledge', is_active: true }],
    })
    if (url.pathname === '/knowledge/files/trash') return json({ entries: [] })
    if (url.pathname === '/favorites') return json({ favorites: [] })
    if (url.pathname === '/privacy') return json({ privacy: [] })
    if (url.pathname === '/knowledge/files') return json({
      tree: [{ name: 'long-scroll.md', path: 'long-scroll.md', isDir: false, mtime: '2026-08-30 12:00', size: markdown.length }],
    })
    if (url.pathname === '/knowledge/files/content') return json({
      path: 'long-scroll.md', content: markdown, mtime: '2026-08-30 12:00', size: markdown.length,
    })
    if (url.pathname === '/knowledge/files/events') {
      return route.fulfill({ status: 200, contentType: 'text/event-stream', body: '' })
    }
    if (request.resourceType() === 'fetch' || request.resourceType() === 'xhr') return json({})
    await route.continue()
  })
  await page.addInitScript(() => {
    localStorage.setItem('agent_editor_theme_mode', 'light')
    localStorage.setItem('agent_editor_profile', JSON.stringify({
      userId: 'split-user', knowledgeDir: 'D:/Knowledge', activeLibraryId: 'default',
      knowledgeLibraries: [{ libraryId: 'default', name: 'Default', knowledgeDir: 'D:/Knowledge', isActive: true }],
    }))
  })

  await page.goto('/')
  await page.getByRole('button', { name: 'Files' }).click()
  await page.getByText('long-scroll.md', { exact: true }).first().click()
  await page.getByRole('button', { name: 'Split' }).click()

  const editor = page.locator('.code-editor-input')
  const preview = page.locator('.markdown-preview .vditor-preview')
  await expect(editor).toBeVisible()
  await expect(preview).toBeVisible()
  await expect.poll(() => editor.evaluate((element) => element.scrollHeight > element.clientHeight)).toBe(true)
  await expect.poll(() => preview.evaluate((element) => element.scrollHeight > element.clientHeight)).toBe(true)
  await page.waitForTimeout(220)

  for (const ratio of [0.25, 0.75, 1]) {
    await setScrollRatio(editor, ratio)
    await expect.poll(() => readScrollRatio(preview)).toBeCloseTo(ratio, 2)
  }

  await page.waitForTimeout(220)
  await setScrollRatio(preview, 0.4)
  await expect.poll(() => readScrollRatio(editor)).toBeCloseTo(0.4, 2)

  if (process.env.METAWEAVE_ACCEPTANCE_SCREENSHOTS === '1') {
    await page.screenshot({ path: testInfo.outputPath('markdown-split-scroll.png'), fullPage: true })
  }
})
