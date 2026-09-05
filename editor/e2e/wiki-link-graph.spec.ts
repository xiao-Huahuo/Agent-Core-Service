/*
 * Rootless knowledge-graph browser smoke tests.
 *
 * Usage:
 * Exercises real Canvas hit-testing, backlink navigation and semantic dragging
 * against deterministic API payloads.
 */

import { expect, test, type Locator, type Page } from '@playwright/test'

const documents: Record<string, string> = Object.fromEntries([
  ['notes/source.md', '# 来源\n\n[[target]]\n\n![[target#摘要]]'],
  ['notes/target.md', '# 目标\n\n## 摘要\n\n嵌入正文'],
  ['notes/isolated.md', '# 独立文档'],
  ...Array.from({ length: 45 }, (_, index) => [
    `notes/isolated-${String(index + 1).padStart(2, '0')}.md`,
    `# 孤立文档 ${index + 1}`,
  ]),
])

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

/** Open the real Canvas context menu for either a document or entity node. */
async function openSemanticNodeMenu(page: Page, canvas: Locator, kind: 'document' | 'entity') {
  const expected = kind === 'document'
    ? ['详情', '打开', '复制名称', '清空节点']
    : ['详情', '复制名称', '删除']
  const hit = await canvas.evaluate(async (element, labels) => {
    const box = element.getBoundingClientRect()
    for (let y = 8; y < box.height - 8; y += 5) {
      for (let x = 8; x < box.width - 8; x += 5) {
        document.body.dispatchEvent(new MouseEvent('click', { bubbles: true }))
        element.dispatchEvent(new PointerEvent('pointermove', {
          bubbles: true, clientX: box.left + x, clientY: box.top + y, pointerId: 7,
        }))
        await Promise.resolve()
        if (!element.classList.contains('hovering')) continue
        element.dispatchEvent(new MouseEvent('contextmenu', {
          bubbles: true, cancelable: true, clientX: box.left + x, clientY: box.top + y,
        }))
        await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()))
        const actual = [...document.querySelectorAll('.graph-node-context-menu button')]
          .map((button) => button.textContent?.trim() ?? '')
        if (JSON.stringify(actual) === JSON.stringify(labels)) return { x: box.left + x, y: box.top + y }
      }
    }
    return null
  }, expected)
  if (!hit) throw new Error(`没有命中${kind === 'document' ? '文档' : '实体'}节点右键菜单`)
  await expect(page.locator('.graph-node-context-menu')).toBeVisible()
  return hit
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
    if (url.pathname === '/favorites') return json({ favorites: [] })
    if (url.pathname === '/privacy') return json({ privacy: [] })
    if (url.pathname === '/sessions' || url.pathname === '/todo/list') return json([])
    if (request.resourceType() === 'fetch' || request.resourceType() === 'xhr') return json({})
    await route.continue()
  })

  await page.addInitScript(() => localStorage.setItem('agent_editor_profile', JSON.stringify({
    userId: 'graph-user', knowledgeDir: 'D:/Knowledge', activeLibraryId: 'default', graphNodeLimit: 2000,
    knowledgeLibraries: [{ libraryId: 'default', name: 'Default', knowledgeDir: 'D:/Knowledge', isActive: true }],
  })))
  await page.goto('/', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'Knowledge graph' }).click()
  await page.getByRole('button', { name: '双向链接' }).click()

  await expect(page.locator('.graph-stat')).toContainText('48 文档 / 1 反向 / 1 嵌入')
  const canvas = page.locator('canvas[aria-label="Knowledge graph canvas"]')
  await expect(canvas).toBeVisible()
  await expect(page.locator('.graph-loading-overlay')).toBeHidden()
  await page.screenshot({ path: testInfo.outputPath('wiki-link-graph.png'), fullPage: true })
  await clickFirstGraphNode(page, canvas)
  await expect(page.locator('.editor-mode-switch')).toBeVisible()
  await expect(page.getByRole('button', { name: /^(?:source|target|isolated|isolated-\d+)$/u })).toBeVisible()
})

test('semantic graph remains responsive after an outward node drag', async ({ page }, testInfo) => {
  const semanticNodes = [
    { id: 'doc', label: '布局说明', kind: 'document', metadata: { relative_path: 'notes/layout.md' } },
    ...Array.from({ length: 10 }, (_, index) => ({
      id: `entity-${index}`, label: `实体 ${index + 1}`, kind: 'entity', entity_type: 'concept',
    })),
  ]
  const semanticLinks = semanticNodes.slice(1).map((entity, index) => ({
    id: `semantic-${index}`, source: 'doc', target: entity.id, kind: 'semantic', weight: 1,
  }))
  const pageErrors: string[] = []
  page.on('pageerror', (error) => pageErrors.push(error.message))
  await page.route('**/*', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const json = (body: unknown) => route.fulfill({ json: body })
    if (url.pathname === '/health') return route.fulfill({ status: 200, body: 'ok' })
    if (url.pathname === '/settings/models/status') return json({ embedding: 'ready', rerank: 'ready' })
    if (url.pathname === '/settings/profile') return json({
      user_id: 'graph-user', knowledge_dir: 'D:/Knowledge', active_library_id: 'default',
      knowledge_libraries: [{ library_id: 'default', name: 'Default', knowledge_dir: 'D:/Knowledge', is_active: true }],
    })
    if (url.pathname === '/knowledge/files/trash') return json({ entries: [] })
    if (url.pathname === '/knowledge/files') return json({ tree: [{
      name: 'notes', path: 'notes', isDir: true, children: [{
        name: 'layout.md', path: 'notes/layout.md', isDir: false, size: 40,
      }],
    }] })
    if (url.pathname === '/knowledge/graph') return json({ nodes: semanticNodes, links: semanticLinks, stats: {} })
    if (url.pathname === '/library/items') return json({ items: [{
      item_id: 'book-1', parent_id: '', item_type: 'book', display_title: '力学说明',
      source_name: 'layout.md', source_path: 'notes/layout.md',
    }], parent: null, breadcrumbs: [] })
    if (url.pathname === '/library/tags') return json({ tags: [] })
    if (url.pathname === '/favorites') return json({ favorites: [] })
    if (url.pathname === '/privacy') return json({ privacy: [] })
    if (url.pathname === '/sessions' || url.pathname === '/todo/list') return json([])
    if (request.resourceType() === 'fetch' || request.resourceType() === 'xhr') return json({})
    await route.continue()
  })
  await page.addInitScript(() => localStorage.setItem('agent_editor_profile', JSON.stringify({
    userId: 'graph-user', knowledgeDir: 'D:/Knowledge', activeLibraryId: 'default', graphNodeLimit: 2000,
    knowledgeLibraries: [{ libraryId: 'default', name: 'Default', knowledgeDir: 'D:/Knowledge', isActive: true }],
  })))

  await page.goto('/', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'Knowledge graph' }).click()
  await page.getByRole('button', { name: '语义' }).click()
  await expect(page.locator('.graph-stat')).toContainText('11 nodes / 10 links')
  const canvas = page.locator('canvas[aria-label="Knowledge graph canvas"]')
  await expect(canvas).toBeVisible()
  await expect(page.locator('.graph-loading-overlay')).toBeHidden()
  await page.screenshot({ path: testInfo.outputPath('semantic-initial-disk.png'), fullPage: true })
  const hit = await canvas.evaluate(async (element) => {
    const box = element.getBoundingClientRect()
    for (let y = 8; y < box.height - 8; y += 6) {
      for (let x = 8; x < box.width - 8; x += 6) {
        element.dispatchEvent(new PointerEvent('pointermove', {
          bubbles: true, clientX: box.left + x, clientY: box.top + y, pointerId: 2,
        }))
        await Promise.resolve()
        if (element.classList.contains('hovering')) return { x: box.left + x, y: box.top + y }
      }
    }
    return null
  })
  if (!hit) throw new Error('没有命中可拖拽的语义图谱节点')
  await page.mouse.move(hit.x, hit.y)
  await page.mouse.down()
  await page.mouse.move(hit.x + 240, hit.y, { steps: 12 })
  await page.waitForTimeout(500)
  await page.mouse.up()
  await page.waitForTimeout(700)

  await expect(canvas).toBeVisible()
  expect(pageErrors).toEqual([])
  await page.screenshot({ path: testInfo.outputPath('semantic-force-drag.png'), fullPage: true })

  await page.getByRole('button', { name: '文件树' }).click()
  await expect(page.locator('.graph-stat')).toContainText('3 nodes / 2 links')
  await expect(canvas).toBeVisible()
  await expect(page.locator('.graph-loading-overlay')).toBeHidden()
  await page.screenshot({ path: testInfo.outputPath('file-tree-semantic-center-icon.png'), fullPage: true })
  await page.getByRole('button', { name: '图书馆' }).click()
  await expect(page.locator('.graph-stat')).toContainText('1 nodes / 0 links')
  await expect(canvas).toBeVisible()
  await expect(page.locator('.graph-loading-overlay')).toBeHidden()
  expect(pageErrors).toEqual([])
  await page.screenshot({ path: testInfo.outputPath('library-semantic-force.png'), fullPage: true })
})

test('semantic nodes expose persisted context actions and the document editor sidebar', async ({ page }, testInfo) => {
  let semanticNodes = [
    { id: 'doc', label: '关系链说明', kind: 'document', metadata: { relative_path: 'notes/chain.md' } },
    { id: 'alpha', label: 'Alpha', kind: 'entity', entity_type: 'concept' },
    { id: 'beta', label: 'Beta', kind: 'entity', entity_type: 'concept' },
    { id: 'gamma', label: 'Gamma', kind: 'entity', entity_type: 'concept' },
  ]
  let semanticLinks = [
    { id: 'mention', source: 'doc', target: 'alpha', kind: 'mentions', weight: 1 },
    { id: 'alpha-beta', source: 'alpha', target: 'beta', kind: 'contains', weight: 1 },
    { id: 'beta-gamma', source: 'beta', target: 'gamma', kind: 'contains', weight: 1 },
  ]
  const mutations: string[] = []
  await page.addInitScript(() => {
    localStorage.setItem('agent_editor_profile', JSON.stringify({
      userId: 'graph-user', knowledgeDir: 'D:/Knowledge', activeLibraryId: 'default', graphNodeLimit: 2000,
      knowledgeLibraries: [{ libraryId: 'default', name: 'Default', knowledgeDir: 'D:/Knowledge', isActive: true }],
    }))
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: async (text: string) => { (window as typeof window & { __copied?: string }).__copied = text } },
    })
  })
  await page.route('**/*', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const json = (body: unknown) => route.fulfill({ json: body })
    if (url.pathname === '/health') return route.fulfill({ status: 200, body: 'ok' })
    if (url.pathname === '/settings/models/status') return json({ embedding: 'ready', rerank: 'ready' })
    if (url.pathname === '/settings/profile') return json({
      user_id: 'graph-user', knowledge_dir: 'D:/Knowledge', active_library_id: 'default',
      knowledge_libraries: [{ library_id: 'default', name: 'Default', knowledge_dir: 'D:/Knowledge', is_active: true }],
    })
    if (url.pathname === '/knowledge/files/trash') return json({ entries: [] })
    if (url.pathname === '/knowledge/files') return json({ tree: [{
      name: 'notes', path: 'notes', isDir: true, children: [{ name: 'chain.md', path: 'notes/chain.md', isDir: false, size: 64 }],
    }] })
    if (url.pathname === '/knowledge/files/content') return json({ path: 'notes/chain.md', content: '# 关系链说明', mtime: '', size: 64 })
    if (url.pathname === '/knowledge/graph' && request.method() === 'GET') {
      return json({ nodes: semanticNodes, links: semanticLinks, stats: {} })
    }
    if (url.pathname.startsWith('/knowledge/graph/nodes/') && request.method() === 'DELETE') {
      const nodeId = decodeURIComponent(url.pathname.split('/').pop() ?? '')
      mutations.push(`delete:${nodeId}`)
      semanticNodes = semanticNodes.filter((node) => node.id !== nodeId)
      semanticLinks = semanticLinks.filter((link) => link.source !== nodeId && link.target !== nodeId)
      return json({ ok: true, deleted_nodes: 1, deleted_edges: 2 })
    }
    if (url.pathname.endsWith('/clear') && request.method() === 'POST') {
      mutations.push('clear:doc')
      semanticNodes = semanticNodes.filter((node) => node.kind === 'document')
      semanticLinks = []
      return json({ ok: true, deleted_nodes: 2, deleted_edges: 1 })
    }
    if (url.pathname === '/favorites') return json({ favorites: [] })
    if (url.pathname === '/privacy') return json({ privacy: [] })
    if (url.pathname === '/sessions' || url.pathname === '/todo/list') return json([])
    if (request.resourceType() === 'fetch' || request.resourceType() === 'xhr') return json({})
    await route.continue()
  })

  await page.goto('/', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'Knowledge graph' }).click()
  const canvas = page.locator('canvas[aria-label="Knowledge graph canvas"]')
  await expect(page.locator('.graph-stat')).toContainText('4 nodes / 3 links')

  await openSemanticNodeMenu(page, canvas, 'entity')
  await expect(page.locator('.graph-node-context-menu button')).toHaveText(['详情', '复制名称', '删除'])
  await page.getByRole('menuitem', { name: '详情' }).click()
  await expect(page.locator('.graph-sidebar')).toHaveClass(/open/u)

  await openSemanticNodeMenu(page, canvas, 'entity')
  await page.getByRole('menuitem', { name: '复制名称' }).click()
  await expect.poll(() => page.evaluate(() => (window as typeof window & { __copied?: string }).__copied)).toBeTruthy()

  await openSemanticNodeMenu(page, canvas, 'entity')
  await page.getByRole('menuitem', { name: '删除' }).click()
  await expect(page.locator('.graph-stat')).toContainText('3 nodes /')
  expect(mutations.some((mutation) => mutation.startsWith('delete:'))).toBe(true)

  await openSemanticNodeMenu(page, canvas, 'document')
  await expect(page.locator('.graph-node-context-menu button')).toHaveText(['详情', '打开', '复制名称', '清空节点'])
  await page.screenshot({ path: testInfo.outputPath('semantic-document-context-menu.png'), fullPage: true })
  await page.getByRole('menuitem', { name: '详情' }).click()
  await expect(page.locator('.selected-node-name')).toContainText('关系链说明')

  await openSemanticNodeMenu(page, canvas, 'document')
  await page.getByRole('menuitem', { name: '复制名称' }).click()
  await expect.poll(() => page.evaluate(() => (window as typeof window & { __copied?: string }).__copied)).toBe('关系链说明')

  await openSemanticNodeMenu(page, canvas, 'document')
  await page.getByRole('menuitem', { name: '打开' }).click()
  await expect(page.locator('.editor-sidebar-content')).toBeVisible()
  await expect(page.locator('.graph-pane')).toBeVisible()

  await openSemanticNodeMenu(page, canvas, 'document')
  await page.getByRole('menuitem', { name: '清空节点' }).click()
  await expect(page.locator('.graph-stat')).toContainText('1 nodes / 0 links')
  await expect(page.locator('.graph-loading-overlay')).toBeHidden()
  expect(mutations).toContain('clear:doc')
  await page.screenshot({ path: testInfo.outputPath('semantic-node-context-actions.png'), fullPage: true })
})
