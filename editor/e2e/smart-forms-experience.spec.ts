/**
 * Smart-table experience browser regression.
 *
 * Usage:
 * Exercises field metadata, figure previews, generation masking, compact rows,
 * PDF covers, typed edge insertion, and joined rectangular selection in Chromium.
 */
import { expect, test } from '@playwright/test'

const PNG_DATA_URL = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAFgQIAKp0P3gAAAABJRU5ErkJggg=='

test('smart table renders typed fields, PDF cover, pending mask, and one joined selection outline', async ({ page }) => {
  await page.setViewportSize({ width: 900, height: 720 })
  const userId = 'smart-form-experience'
  const columns = [
    { id: 'row_index', title: '序号', type: 'index', removable: false, editable: false, width: 64 },
    { id: 'literature_file', title: '文献上传', type: 'file', removable: true, editable: false, width: 168 },
    { id: 'literature_content', title: '文献内容', type: 'readonly_text', removable: true, editable: false, width: 240 },
    { id: 'figures', title: '图表', type: 'readonly_text', removable: true, editable: false, width: 240 },
    { id: 'formulas', title: '公式', description: '提取主要 LaTeX 数学公式并使用 $$...$$ 包裹。', type: 'smart_text', removable: true, editable: true, width: 260, tone: 'violet' },
    { id: 'title', title: '标题', description: '提取论文首页的正式标题', type: 'smart_text', removable: false, editable: true, width: 230, tone: 'blue' },
    { id: 'keywords', title: '关键词', type: 'smart_text', removable: true, editable: true, width: 180, tone: 'violet' },
    { id: 'abstract', title: '摘要', type: 'smart_text', removable: true, editable: true, width: 260, tone: 'blue' },
  ]
  const rows = Array.from({ length: 3 }, (_, index) => ({
    id: `row-${index + 1}`,
    height: 1,
    cells: Object.fromEntries(columns.map((column) => [column.id, {
      value: column.id === 'title'
        ? `原标题 ${index + 1}`
        : column.id === 'literature_content'
          ? `文献内容 ${index + 1}${'。'.repeat(240)}`
          : column.id === 'figures'
            ? index === 0 ? `![图表 1](/.mw/assets/paper/image_1.png)\n\n${'图表说明。'.repeat(50)}` : ''
            : column.id === 'formulas'
              ? index === 0 ? Array.from({ length: 16 }, (_, formulaIndex) => `$$E_${formulaIndex} = mc^2 + \\frac{p^2}{2m}$$`).join('\n\n') : ''
            : '',
      status: column.type === 'smart_text' ? 'ready' : undefined,
      ...(column.id === 'literature_file' && index === 0 ? {
        value: 'paper.pdf',
        fileName: 'paper.pdf',
        assetPath: '.mw/forms/体验表/assets/paper.pdf',
      } : {}),
    }])),
  }))
  const form = { version: 1, title: '体验表', updatedAt: new Date().toISOString(), columns, rows }

  await page.route('**/*', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    if (url.pathname === '/health') return route.fulfill({ status: 200, body: 'ok' })
    if (url.pathname === '/settings/models/status') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ embedding: 'ready', rerank: 'ready' }) })
    }
    if (url.pathname === '/settings/profile') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ user_id: userId, knowledge_dir: 'D:/Knowledge', active_library_id: 'default', knowledge_libraries: [] }) })
    }
    if (request.method() === 'GET' && url.pathname === '/smart-forms/list') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([{ form_id: 'sf_experience', title: '体验表', asset_dir: '.mw/forms/体验表', updated_at: form.updatedAt }]) })
    }
    if (request.method() === 'GET' && url.pathname === '/smart-forms/sf_experience') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ form_id: 'sf_experience', user_id: userId, asset_dir: '.mw/forms/体验表', form, updated_at: form.updatedAt }) })
    }
    if (request.method() === 'POST' && url.pathname === '/smart-forms/save') {
      const payload = request.postDataJSON() as { form: unknown }
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ form_id: 'sf_experience', user_id: userId, asset_dir: '.mw/forms/体验表', form: payload.form, updated_at: new Date().toISOString() }) })
    }
    if (request.method() === 'GET' && url.pathname === '/knowledge/files/preview') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ path: url.searchParams.get('path'), kind: 'pdf', thumbnail_url: PNG_DATA_URL, raw_url: '/knowledge/raw/paper.pdf', mtime: form.updatedAt, size: 128, extension: '.pdf', readonly: true }) })
    }
    if (request.method() === 'GET' && url.pathname === '/knowledge/files/raw') {
      return route.fulfill({ status: 200, contentType: 'image/png', body: Buffer.from(PNG_DATA_URL.split(',')[1]!, 'base64') })
    }
    if (request.method() === 'POST' && url.pathname === '/structured-generation/fields') {
      await new Promise((resolve) => setTimeout(resolve, 600))
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ raw_output: 'invalid', results: [{ field_id: 'title', status: 'failed', value: '', error: 'invalid result' }] }) })
    }
    return route.continue()
  })

  await page.addInitScript(({ profile }) => localStorage.setItem('agent_editor_profile', JSON.stringify(profile)), {
    profile: { userId, knowledgeDir: 'D:/Knowledge', activeLibraryId: 'default', knowledgeLibraries: [] },
  })
  await page.goto('/')
  await page.getByRole('button', { name: '库', exact: true }).hover()
  await page.getByRole('button', { name: '智能表格' }).click()

  const headers = page.locator('.smart-table thead tr:nth-child(2) th')
  await expect(headers).toHaveCount(columns.length)
  await expect(headers.locator('.column-field-icon')).toHaveCount(columns.length)
  await expect(headers.locator('.column-type-pill')).toHaveCount(columns.length)
  await expect(headers.locator('.column-ai-pill')).toHaveCount(4)
  await expect(headers.locator('.column-actions')).toHaveCount(0)
  expect((await headers.first().boundingBox())?.width).toBeLessThanOrEqual(33)
  expect((await headers.first().boundingBox())?.height).toBeLessThan(42)
  await expect(page.locator('.smart-table tbody tr').first()).toHaveAttribute('style', /height: 37px/)

  const figureCell = page.locator('td[data-row-id="row-1"][data-column-id="figures"]')
  const figurePreview = figureCell.locator('img[alt^="图表"]')
  const figureToggle = figureCell.locator('.smart-markdown-toggle')
  await expect(figurePreview).toBeVisible()
  await figureToggle.click()
  await expect(figurePreview).toBeVisible()
  await figureToggle.click()
  await expect(figureCell.locator('.smart-markdown-cell')).not.toHaveClass(/collapsing/)
  await expect(figurePreview).toBeVisible()

  const formulaCell = page.locator('td[data-row-id="row-1"][data-column-id="formulas"]')
  const formulaPreview = formulaCell.locator('.katex-display').first()
  const formulaToggle = formulaCell.locator('.smart-markdown-toggle')
  await expect(formulaPreview).toBeVisible()
  await formulaToggle.click()
  await expect(formulaPreview).toBeVisible()
  await formulaToggle.click()
  await expect(formulaCell.locator('.smart-markdown-cell')).not.toHaveClass(/collapsing/)
  await expect(formulaPreview).toBeVisible()

  const titleDescriptionToggle = page.locator('th[data-column-id="title"] .column-description-toggle')
  await titleDescriptionToggle.click()
  await expect(page.locator('th[data-column-id="title"] .column-description-text')).toHaveText('提取论文首页的正式标题')
  await expect(page.locator('th[data-column-id="row_index"] .column-description-toggle')).toHaveCount(0)

  const literatureRow = page.locator('.smart-table tbody tr').nth(1)
  const literatureToggle = page.locator('td[data-row-id="row-2"][data-column-id="literature_content"] .smart-markdown-toggle')
  const collapsedHeight = (await literatureRow.boundingBox())?.height ?? 0
  await literatureToggle.click()
  await expect.poll(async () => (await literatureRow.boundingBox())?.height ?? 0).toBeGreaterThanOrEqual(282)
  await page.waitForTimeout(240)
  await literatureToggle.click()
  await page.waitForTimeout(100)
  const closingHeight = (await literatureRow.boundingBox())?.height ?? 0
  expect(closingHeight).toBeGreaterThan(collapsedHeight)
  expect(closingHeight).toBeLessThan(282)
  await expect(literatureRow).toHaveAttribute('style', /height: 37px/)
  await page.waitForTimeout(320)
  expect((await literatureRow.boundingBox())?.height).toBeLessThanOrEqual(collapsedHeight + 1)

  const tableFrame = page.locator('.table-frame')
  const tableDimensions = await tableFrame.evaluate((element) => ({ clientWidth: element.clientWidth, scrollWidth: element.scrollWidth }))
  expect(tableDimensions.scrollWidth).toBeGreaterThan(tableDimensions.clientWidth)
  await tableFrame.evaluate((element) => { element.scrollLeft = 240 })
  const frameBox = await tableFrame.boundingBox()
  const stickyFileBox = await headers.nth(1).boundingBox()
  expect(Math.abs((stickyFileBox?.x ?? 0) - (frameBox?.x ?? 0))).toBeLessThanOrEqual(2)
  await tableFrame.evaluate((element) => { element.scrollLeft = 0 })
  await page.setViewportSize({ width: 1280, height: 720 })

  const pdfPreview = page.locator('.file-preview-image')
  await expect(pdfPreview).toBeVisible()
  await expect(pdfPreview).toHaveCSS('object-fit', 'contain')
  expect((await pdfPreview.boundingBox())?.width).toBeGreaterThan(120)

  const titleCell = page.locator('td[data-row-id="row-1"][data-column-id="title"]')
  await titleCell.click({ button: 'right' })
  await page.getByRole('button', { name: '智能填充', exact: true }).click()
  await expect(titleCell.locator('.smart-cell-loading-mask')).toBeVisible()
  await expect(titleCell.locator('.pixel-loader i')).toHaveCount(5)
  await expect(titleCell.locator('.smart-cell-loading-mask')).toBeHidden()
  await expect(titleCell.locator('textarea')).toHaveValue('原标题 1')

  const secondTitleCell = page.locator('td[data-row-id="row-2"][data-column-id="title"]')
  await secondTitleCell.click({ button: 'right' })
  await page.getByRole('button', { name: '行移动', exact: true }).hover()
  await page.getByRole('button', { name: '行上移', exact: true }).click()
  await expect(page.locator('td[data-column-id="title"] textarea').first()).toHaveValue('原标题 2')

  const headerOrder = () => headers.evaluateAll((items) => items.map((item) => item.getAttribute('data-column-id')))
  const columnOrderBefore = await headerOrder()
  await page.locator('th[data-column-id="keywords"]').click({ button: 'right' })
  await page.getByRole('button', { name: '列移动', exact: true }).hover()
  await page.getByRole('button', { name: '列左移', exact: true }).click()
  const columnOrderAfter = await headerOrder()
  expect(columnOrderAfter.indexOf('keywords')).toBe(columnOrderBefore.indexOf('keywords') - 1)

  await page.locator('td[data-row-id="row-2"][data-column-id="title"]').click({ button: 'right' })
  await page.getByRole('button', { name: '行移动', exact: true }).hover()
  await page.getByRole('button', { name: '行下移', exact: true }).click()
  await page.locator('th[data-column-id="keywords"]').click({ button: 'right' })
  await page.getByRole('button', { name: '列移动', exact: true }).hover()
  await page.getByRole('button', { name: '列右移', exact: true }).click()

  const headerCountBefore = await headers.count()
  const addRowButton = page.locator('.table-edge-add-row')
  const addColumnButton = page.locator('.table-edge-add-column')
  await expect(addRowButton).toHaveCSS('border-top-width', '0px')
  await expect(addColumnButton).toHaveCSS('border-left-width', '0px')
  const idleRowBackground = await addRowButton.evaluate((element) => getComputedStyle(element).backgroundColor)
  const idleColumnBackground = await addColumnButton.evaluate((element) => getComputedStyle(element).backgroundColor)
  await addRowButton.hover()
  expect(await addRowButton.evaluate((element) => getComputedStyle(element).backgroundColor)).not.toBe(idleRowBackground)
  await addColumnButton.hover()
  expect(await addColumnButton.evaluate((element) => getComputedStyle(element).backgroundColor)).not.toBe(idleColumnBackground)
  await addColumnButton.click()
  await expect(headers).toHaveCount(headerCountBefore)
  const edgeMenu = page.locator('.edge-column-menu')
  await expect(edgeMenu).toBeVisible()
  await expect(edgeMenu.locator('.menu-column-type-pill')).toHaveCount(18)
  await expect(edgeMenu.locator('button .ic-icon')).toHaveCount(25)
  const customFieldNameInput = edgeMenu.getByPlaceholder('例如：备注')
  await expect(edgeMenu.getByText('辅助描述', { exact: true })).toBeVisible()
  await expect(edgeMenu.getByPlaceholder('例如：提取作者明确陈述的局限')).toBeVisible()
  await expect(customFieldNameInput).toHaveCSS('border-top-width', '0px')
  await customFieldNameInput.focus()
  await page.waitForTimeout(200)
  expect(await customFieldNameInput.evaluate((element) => getComputedStyle(element).boxShadow)).toContain('4px')
  await edgeMenu.locator('button').filter({ hasText: '重要性' }).click()
  await expect(headers).toHaveCount(headerCountBefore + 1)

  const rowsBeforeUpload = await page.locator('.smart-table tbody tr').count()
  const fileChooserPromise = page.waitForEvent('filechooser')
  await page.getByRole('button', { name: '上传文献', exact: true }).click()
  await fileChooserPromise
  await expect(page.locator('.smart-table tbody tr')).toHaveCount(rowsBeforeUpload + 1)

  await page.setViewportSize({ width: 1800, height: 720 })
  const dragStart = page.locator('td[data-row-id="row-1"][data-column-id="title"]')
  const dragEnd = page.locator('td[data-row-id="row-3"][data-column-id="abstract"]')
  const startBox = await dragStart.boundingBox()
  const endBox = await dragEnd.boundingBox()
  expect(startBox).not.toBeNull()
  expect(endBox).not.toBeNull()
  await page.mouse.move(startBox!.x + 8, startBox!.y + 8)
  await page.mouse.down()
  await page.mouse.move(endBox!.x + 8, endBox!.y + 8, { steps: 8 })
  await page.mouse.up()
  await expect(page.locator('td.selected')).toHaveCount(9)
  const centerCell = page.locator('td[data-row-id="row-2"][data-column-id="keywords"]')
  await expect(centerCell).toHaveCSS('box-shadow', 'none')
  expect(await dragStart.evaluate((element) => getComputedStyle(element).boxShadow)).not.toBe('none')

  await page.locator('.file-picker').first().click()
  await expect(page.locator('.smart-forms-view')).toBeVisible()
  await expect(page.locator('.editor-sidebar-content .editor-panel')).toBeVisible()
  await expect(page.locator('.editor-sidebar-content .editor-mode-switch')).toBeVisible()
  await expect(page.locator('.editor-sidebar-content .sidebar-close-button')).toBeVisible()
})
