import { expect, test, type Locator, type Page } from '@playwright/test'

const documents: Record<string, string> = {
  'notes/source.md': '# 来源\n\n[[target]]\n\n![[target#摘要]]',
  'notes/target.md': '# 目标\n\n## 摘要\n\n嵌入正文',
  'notes/isolated.md': '# 独立文档',
}

/** Finds a rendered Canvas node through the component's real hover hit-test. */
async function clickFirstGraphNode(page: Page, canvas: Locator) {
  const hit = await canvas.evaluate(async (element) => {
    const box = element.getBoundingClientRect()
    for (let y = 8; y < box.height - 8; y += 6) {
      for (let x = 8; x < box.width - 8; x += 6) {
        element.dispatchEvent(new PointerEvent('pointermove', {
          bubbles: true,
          clientX: box.left + x,
          clientY: box.top + y,
          pointerId: 1,
        }))
        await Promise.resolve()
        if (element.classList.contains('hovering')) return { x: box.left + x, y: box.top + y }
      }
    }
    return null
  })
  if (!hit) throw new Error('没有命中可点击的双向链接图谱节点')
  await page.mouse.click(hit.x, hit.y)
}

test('bidirectional-link graph counts both wiki edge kinds and opens a clicked document', async ({ page }, testInfo) => {
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
      user_id: 'graph-user', knowledge_dir: 'D:/Knowledge', active_library_id: 'default',
      knowledge_libraries: [{ library_id: 'default', name: 'Default', knowledge_dir: 'D:/Knowledge', is_active: true }],
    })
    if (url.pathname === '/knowledge/files/trash') return json({ entries: [] })
    if (url.pathname === '/knowledge/files') return json({
      tree: [{
        name: 'notes', path: 'notes', isDir: true, children: Object.keys(documents).map((filePath) => ({
          name: filePath.split('/').pop(), path: filePath, isDir: false, size: 40,
        })),
      }],
    })
    if (url.pathname === '/knowledge/files/content') return json({
      path, content: documents[path] ?? '', mtime: '2026-08-17 17:00', size: 40,
    })
    if (url.pathname === '/knowledge/graph') return json({ nodes: [], links: [] })
    if (request.resourceType() === 'fetch' || request.resourceType() === 'xhr') return json({})
    await route.continue()
  })

  await page.addInitScript(() => localStorage.setItem('agent_editor_profile', JSON.stringify({
    userId: 'graph-user', knowledgeDir: 'D:/Knowledge', activeLibraryId: 'default', graphNodeLimit: 2000,
    knowledgeLibraries: [{ libraryId: 'default', name: 'Default', knowledgeDir: 'D:/Knowledge', isActive: true }],
  })))
  await page.goto('/')
  await page.getByRole('button', { name: 'Knowledge graph' }).click()
  await page.getByRole('button', { name: '双向链接' }).click()

  await expect(page.locator('.graph-stat')).toContainText('3 文档 / 1 反向 / 1 嵌入')
  const canvas = page.locator('canvas[aria-label="Knowledge graph canvas"]')
  await expect(canvas).toBeVisible()
  await expect(page.locator('.graph-loading-overlay')).toBeHidden()
  await page.screenshot({ path: testInfo.outputPath('wiki-link-graph.png'), fullPage: true })
  await clickFirstGraphNode(page, canvas)
  await expect(page.locator('.editor-mode-switch')).toBeVisible()
  await expect(page.getByRole('button', { name: /^(?:source|target|isolated)$/u })).toBeVisible()
})
