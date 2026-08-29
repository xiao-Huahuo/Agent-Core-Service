/**
 * Four-library unified-search responsive browser smoke test.
 *
 * Usage:
 * Runs against the real Vite application while intercepting only the search
 * response so no user business data is created. It captures desktop, tablet,
 * mobile, and extra-narrow screenshots for both result presentations.
 */

import { expect, test } from '@playwright/test'

const fileResult = {
  id: 'docs/research-notes.md', source: 'files', title: 'research-notes.md', snippet: '联合搜索的正文片段',
  locator: 'docs/research-notes.md', updated_at: '2026-08-29T10:00:00', score: 0.94,
  matched_modes: ['title', 'fulltext'], item: { name: 'research-notes.md', path: 'docs/research-notes.md', isDir: false, size: 18432 },
}
const libraryResult = {
  id: 'book-1', source: 'library', title: '知识检索手册', snippet: '图书馆描述与真实书籍正文',
  locator: 'docs/search-handbook.pdf', updated_at: '2026-08-29T09:00:00', score: 0.89,
  matched_modes: ['fulltext', 'semantic'], item: {
    item_id: 'book-1', user_id: 'search-smoke', library_id: 'lib-1', parent_id: '', item_type: 'book',
    content_type: 'knowledge_file', title: '知识检索手册', display_title: '知识检索手册', description: '四库联合搜索设计',
    source_path: 'docs/search-handbook.pdf', source_url: '', source_name: 'search-handbook.pdf', source_mime: 'application/pdf',
    source_size: 2048, source_mtime: '2026-08-29T09:00:00', source_exists: true, cover_mode: 'title', cover_asset_id: '',
    cover_asset: null, tags: ['搜索'], child_count: 0, index_status: 'indexed', graph_status: 'graphed', created_at: '', updated_at: '',
  },
}
const componentResult = {
  id: 'cards/SearchPanel.vue', source: 'components', title: 'SearchPanel', snippet: '<section class="search-panel">',
  locator: 'cards/SearchPanel.vue', updated_at: '2026-08-29T08:00:00', score: 0.84,
  matched_modes: ['semantic'], item: {
    component_id: 'cards/SearchPanel.vue', user_id: 'search-smoke', title: 'SearchPanel', tag: 'cards', source_format: 'vue',
    source: '<template><section style="padding:24px">Search Panel</section></template>', builtin: false, created_at: null, updated_at: null,
  },
}
const literatureResult = {
  id: 'form-1:row-1', source: 'literature', title: 'Semantic Retrieval Study', snippet: '文献完整正文中的语义召回证据',
  locator: '.mw/forms/paper.pdf', updated_at: '2026-08-29T07:00:00', score: 0.8,
  matched_modes: ['fulltext', 'semantic'], item: {
    form_id: 'form-1', form_title: '研究文献', row_id: 'row-1', title: 'Semantic Retrieval Study', file_name: 'paper.pdf',
    asset_path: '.mw/forms/paper.pdf', content_excerpt: '文献完整正文中的语义召回证据', file_size: 4096,
    entered_at: '2026-08-29T07:00:00', updated_at: '2026-08-29T07:00:00', last_viewed_at: '', tags: ['RAG'], rating: 5,
  },
}
const results = [fileResult, libraryResult, componentResult, literatureResult]

test('renders unified and vertically split results at four responsive widths', async ({ page }, testInfo) => {
  await page.addInitScript(() => {
    const originalFetch = window.fetch.bind(window)
    window.fetch = (input, init) => String(input).endsWith('/health')
      ? Promise.resolve(new Response('{"status":"ok"}', { status: 200, headers: { 'content-type': 'application/json' } }))
      : originalFetch(input, init)
  })
  await page.route('**/health', (route) => route.fulfill({ status: 200, body: '{"status":"ok"}' }))
  await page.route((url) => url.pathname === '/settings/profile', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      user_id: 'search-smoke', knowledge_dir: 'D:/Knowledge', active_library_id: 'lib-1',
      active_knowledge_library: { library_id: 'lib-1', user_id: 'search-smoke', name: 'knowledge', knowledge_dir: 'D:/Knowledge', is_active: true, created_at: '', updated_at: '' },
      knowledge_libraries: [{ library_id: 'lib-1', user_id: 'search-smoke', name: 'knowledge', knowledge_dir: 'D:/Knowledge', is_active: true, created_at: '', updated_at: '' }],
      created_at: '', updated_at: '',
    }),
  }))
  await page.route((url) => url.pathname === '/search', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      query: 'search', selected_sources: ['files', 'library', 'components', 'literature'], fulltext: true, semantic: true,
      results,
      groups: { files: [fileResult], library: [libraryResult], components: [componentResult], literature: [literatureResult] },
      counts: { files: 1, library: 1, components: 1, literature: 1 }, total: 4,
    }),
  }))
  await page.route((url) => url.pathname === '/knowledge/files/preview', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      path: 'docs/research-notes.md', kind: 'text', content: '联合搜索的正文片段',
      mtime: '2026-08-29T10:00:00', size: 18432, extension: '.md', readonly: true,
    }),
  }))
  await page.route((url) => url.pathname === '/knowledge/files/content', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ path: 'docs/research-notes.md', content: '联合搜索的正文片段', mtime: '2026-08-29T10:00:00', size: 18432 }),
  }))
  await page.route((url) => url.pathname === '/library/tags', (route) => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify({ tags: [] }),
  }))
  await page.route((url) => url.pathname === '/smart-forms/form-1', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      form_id: 'form-1', user_id: 'search-smoke', asset_dir: '', updated_at: '',
      form: {
        id: 'form-1', title: '研究文献',
        columns: [{ id: 'title', title: '标题', type: 'text', editable: true }],
        rows: [{ id: 'row-1', createdAt: '2026-08-29T07:00:00', updatedAt: '2026-08-29T07:00:00', cells: { title: { value: 'Semantic Retrieval Study' } } }],
      },
    }),
  }))
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/')
  const userIdInput = page.getByRole('textbox', { name: '用户 ID' })
  await expect(userIdInput.or(page.locator('.topbar'))).toBeVisible()
  if (await userIdInput.isVisible()) {
    await userIdInput.fill('search-smoke')
    await page.getByRole('button', { name: '进入', exact: true }).click()
  }

  await page.getByRole('button', { name: '库', exact: true }).click()
  const libraryIconColors = await page.locator('[aria-label="知识库菜单"] .library-entry-icon').evaluateAll((icons) => (
    icons.map((icon) => getComputedStyle(icon).color)
  ))
  expect(new Set(libraryIconColors).size).toBe(6)
  await page.screenshot({ path: testInfo.outputPath('library-menu-colors.png'), fullPage: true })
  await page.getByRole('button', { name: '库', exact: true }).click()

  await page.getByRole('button', { name: '搜索', exact: true }).click()
  const toolbarDropdown = page.locator('.search-dropdown:not(.page-search-dropdown)')
  await expect(toolbarDropdown).toBeVisible()
  await expect(toolbarDropdown.locator('.source-toggle-icon')).toHaveCount(4)
  await expect(toolbarDropdown.locator('.source-toggle-label')).toHaveCount(0)
  const toolbarSourceColors = await toolbarDropdown.locator('.source-toggle-icon').evaluateAll((icons) => (
    icons.map((icon) => getComputedStyle(icon).color)
  ))
  expect(toolbarSourceColors).toEqual([libraryIconColors[0], libraryIconColors[1], libraryIconColors[2], libraryIconColors[5]])
  await page.screenshot({ path: testInfo.outputPath('toolbar-source-icons.png'), fullPage: true })
  await toolbarDropdown.locator('.source-toggle-btn').first().click()
  await expect(toolbarDropdown).toBeVisible()
  await toolbarDropdown.locator('.source-toggle-btn').first().click()
  await expect.poll(async () => {
    const [anchor, dropdown] = await Promise.all([
      page.locator('.search-wrapper:not(.page-variant)').boundingBox(),
      toolbarDropdown.boundingBox(),
    ])
    return Boolean(anchor && dropdown && Math.abs(dropdown.x - anchor.x) < 1 && Math.abs(dropdown.y - (anchor.y + anchor.height + 4)) < 1)
  }).toBe(true)

  await page.getByRole('button', { name: 'Search', exact: true }).click()
  await page.locator('.page-variant .search-input').fill('search')
  await page.locator('.search-box-submit').click()
  await expect(page.locator('.unified-result-row')).toHaveCount(4)
  await expect(page.locator('.result-source')).toHaveCount(4)
  expect((await page.locator('.result-source').allTextContents()).every((text) => !text.includes('来自'))).toBe(true)
  await expect(page.locator('.source-result-icon')).toHaveCount(4)

  await page.locator('.page-variant .search-input').focus()
  const pageDropdown = page.locator('.page-search-dropdown')
  await pageDropdown.locator('.source-toggle-btn').nth(2).click()
  await expect(pageDropdown).toBeVisible()
  await pageDropdown.locator('.source-toggle-btn').nth(2).click()
  await expect(pageDropdown).toBeVisible()
  await page.locator('.search-page').dispatchEvent('mousedown')
  await expect(pageDropdown).toBeHidden()

  await page.locator('.unified-result-row').first().click()
  await expect(page.locator('.editor-sidebar-content')).toHaveAttribute('aria-hidden', 'false')
  await expect(page.locator('.sidebar-editor-panel .code-editor-input')).toBeEditable()
  await page.screenshot({ path: testInfo.outputPath('file-editor-sidebar-desktop.png'), fullPage: true })
  await page.locator('.page-variant .search-input').focus()
  await page.locator('.page-variant .search-input').fill('')
  await expect(page.locator('.editor-sidebar-content')).toHaveAttribute('aria-hidden', 'true')
  await expect(pageDropdown).toBeVisible()
  await expect.poll(async () => {
    const [anchor, dropdown] = await Promise.all([
      page.locator('.page-variant.search-wrapper').boundingBox(),
      pageDropdown.boundingBox(),
    ])
    return Boolean(anchor && dropdown && Math.abs(dropdown.x - anchor.x) < 1 && Math.abs(dropdown.y - (anchor.y + anchor.height + 4)) < 1)
  }).toBe(true)
  await page.locator('.page-variant .search-input').fill('search')
  await expect(page.locator('.unified-result-row')).toHaveCount(4)
  await page.locator('.search-page').dispatchEvent('mousedown')
  await expect(pageDropdown).toBeHidden()

  const searchGeometryBefore = await page.evaluate(() => {
    const stage = document.querySelector('.search-stage')!.getBoundingClientRect()
    const bar = document.querySelector('.page-variant .search-bar')!.getBoundingClientRect()
    return [stage.x, stage.y, stage.width, stage.height, bar.x, bar.y, bar.width, bar.height].map((value) => Math.round(value * 100) / 100)
  })
  const indicatorXBefore = (await page.locator('.presentation-indicator').boundingBox())!.x
  await expect(page.locator('.presentation-indicator')).not.toHaveCSS('transition-duration', '0s')
  await page.getByRole('button', { name: '分裂样式' }).click()
  await expect(page.locator('.presentation-indicator')).toHaveClass(/split/)
  await expect.poll(async () => (await page.locator('.presentation-indicator').boundingBox())!.x).toBeGreaterThan(indicatorXBefore + 20)
  const searchGeometryAfter = await page.evaluate(() => {
    const stage = document.querySelector('.search-stage')!.getBoundingClientRect()
    const bar = document.querySelector('.page-variant .search-bar')!.getBoundingClientRect()
    return [stage.x, stage.y, stage.width, stage.height, bar.x, bar.y, bar.width, bar.height].map((value) => Math.round(value * 100) / 100)
  })
  expect(searchGeometryAfter).toEqual(searchGeometryBefore)
  await page.getByRole('button', { name: '统一样式' }).click()

  const sidebarClose = page.getByRole('button', { name: '关闭编辑区侧边栏' })
  await page.locator('.unified-result-row').nth(1).click()
  await expect(page.locator('.search-result-sidebar[data-source="library"]')).toBeVisible()
  await expect(page.locator('.search-result-sidebar[data-source="library"] .dialog-panel.embedded input').first()).toBeEditable()
  const sidebarWidthBefore = (await page.locator('.editor-sidebar-content').boundingBox())!.width
  const editorResizer = page.getByRole('separator', { name: 'Resize editor sidebar' })
  const resizerBox = await editorResizer.boundingBox()
  await page.mouse.move((resizerBox?.x ?? 0) + 2, (resizerBox?.y ?? 0) + 200)
  await page.mouse.down()
  await page.mouse.move((resizerBox?.x ?? 0) - 70, (resizerBox?.y ?? 0) + 200)
  await page.mouse.up()
  await expect.poll(async () => (await page.locator('.editor-sidebar-content').boundingBox())!.width).toBeGreaterThan(sidebarWidthBefore + 50)
  await page.screenshot({ path: testInfo.outputPath('library-editor-sidebar-desktop.png'), fullPage: true })
  await sidebarClose.click()

  await page.locator('.unified-result-row').nth(2).click()
  await expect(page.locator('.search-result-sidebar[data-source="components"] .detail-workbench.compact')).toBeVisible()
  await expect(page.locator('.sidebar-component-editor .code-editor-input')).toBeEditable()
  await expect.poll(async () => (await page.locator('.editor-sidebar-content').boundingBox())!.width).toBeGreaterThan(500)
  await page.screenshot({ path: testInfo.outputPath('component-editor-sidebar-desktop.png'), fullPage: true })
  await sidebarClose.click()

  await page.locator('.unified-result-row').nth(3).click()
  await expect(page.locator('.search-result-sidebar[data-source="literature"] .literature-card.expanded')).toBeVisible()
  await expect(page.locator('.sidebar-literature-editor input, .sidebar-literature-editor textarea').first()).toBeEditable()
  await expect.poll(async () => (await page.locator('.editor-sidebar-content').boundingBox())!.width).toBeGreaterThan(500)
  await page.screenshot({ path: testInfo.outputPath('literature-editor-sidebar-desktop.png'), fullPage: true })
  await page.getByRole('button', { name: '查看文献内容' }).click()
  await expect(page.locator('.sidebar-literature-content.editor-panel')).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('literature-content-sidebar-desktop.png'), fullPage: true })
  await page.getByRole('button', { name: '查看字段明细' }).click()
  await expect(page.locator('.sidebar-literature-editor')).toBeVisible()
  await sidebarClose.click()

  const widths = [
    { name: 'desktop', width: 1440, height: 900 },
    { name: 'tablet', width: 768, height: 1024 },
    { name: 'mobile', width: 390, height: 844 },
    { name: 'narrow', width: 320, height: 720 },
  ]
  for (const viewport of widths) {
    await page.setViewportSize({ width: viewport.width, height: viewport.height })
    if (viewport.name === 'mobile') {
      await page.locator('.page-variant .search-input').focus()
      await expect(page.locator('.source-toggle-btn')).toHaveCount(4)
      const filterBounds = await page.locator('.page-search-dropdown').boundingBox()
      expect((filterBounds?.x ?? 0) + (filterBounds?.width ?? 0)).toBeLessThanOrEqual(viewport.width)
      await page.screenshot({ path: testInfo.outputPath('filters-mobile.png'), fullPage: true })
      await page.locator('.search-page').dispatchEvent('mousedown')
      await expect(page.locator('.page-search-dropdown')).toBeHidden()
      await page.locator('.unified-result-row').nth(2).click()
      await expect(page.locator('.editor-sidebar-content')).toHaveCSS('position', 'fixed')
      await expect(page.locator('.search-result-sidebar[data-source="components"]')).toBeVisible()
      await expect.poll(() => page.evaluate(
        () => document.querySelector('.editor-sidebar-content')!.getBoundingClientRect().right,
      )).toBeLessThanOrEqual(viewport.width)
      await page.screenshot({ path: testInfo.outputPath('component-sidebar-mobile.png'), fullPage: true })
      await page.getByRole('button', { name: '关闭编辑区侧边栏' }).click()
    }
    await page.screenshot({ path: testInfo.outputPath(`unified-${viewport.name}.png`), fullPage: true })
    const dimensions = await page.locator('.search-page').evaluate((element) => {
      const bounds = element.getBoundingClientRect()
      const overflow = [...element.querySelectorAll<HTMLElement>('*')]
        .filter((child) => child.getBoundingClientRect().right > bounds.right + 1)
        .slice(0, 4)
        .map((child) => `${child.className}:${Math.round(child.getBoundingClientRect().right - bounds.right)}`)
      return { scroll: element.scrollWidth, client: element.clientWidth, overflow }
    })
    expect(dimensions.scroll, `${viewport.name} unified overflow ${dimensions.overflow.join(',')}`).toBeLessThanOrEqual(dimensions.client)
  }

  await page.setViewportSize({ width: 1440, height: 900 })
  await page.getByRole('button', { name: '分裂样式' }).click()
  await expect(page.locator('.split-section')).toHaveCount(4)
  await expect(page.locator('.search-file-medium-tile')).toBeVisible()
  await expect(page.locator('.literature-file-list .expand-button')).toHaveCount(0)
  const fileTileVisual = await page.locator('.search-file-medium-tile').first().evaluate((tile) => {
    const icon = tile.querySelector('.material-file-icon-medium')!
    const name = tile.querySelector('.tile-name')!
    const size = tile.querySelector('small')!
    return {
      iconWidth: icon.getBoundingClientRect().width,
      nameHeight: name.getBoundingClientRect().height,
      tileFont: Number.parseFloat(getComputedStyle(tile).fontSize),
      sizeFont: Number.parseFloat(getComputedStyle(size).fontSize),
      lineClamp: getComputedStyle(name).webkitLineClamp,
    }
  })
  expect(fileTileVisual.iconWidth).toBeGreaterThanOrEqual(50)
  expect(fileTileVisual.nameHeight).toBeGreaterThan(20)
  expect(fileTileVisual.sizeFont).toBeLessThan(fileTileVisual.tileFont)
  expect(fileTileVisual.lineClamp).toBe('2')
  await expect(page.locator('.library-card')).toBeVisible()
  await expect(page.locator('.component-card')).toBeVisible()
  await expect(page.locator('.literature-card')).toBeVisible()
  const sectionY = await page.locator('.split-section').evaluateAll((sections) => sections.map((section) => section.getBoundingClientRect().y))
  expect(sectionY).toEqual([...sectionY].sort((left, right) => left - right))

  for (const viewport of widths) {
    await page.setViewportSize({ width: viewport.width, height: viewport.height })
    await page.screenshot({ path: testInfo.outputPath(`split-${viewport.name}.png`), fullPage: true })
    const dimensions = await page.locator('.search-page').evaluate((element) => ({ scroll: element.scrollWidth, client: element.clientWidth }))
    expect(dimensions.scroll, `${viewport.name} split overflow`).toBeLessThanOrEqual(dimensions.client)
  }
})
