/**
 * Component library real-browser smoke test.
 *
 * Usage:
 * Runs against the real Vite proxy and backend, verifies all built-in cards,
 * masonry sizing, component interaction, detail workbench, toolbar placement,
 * sidebar filtering, responsive upload layout, and an interactive Vue preview.
 */

import { expect, test } from '@playwright/test'

const seededComponentPaths: string[] = []

test.afterEach(async ({ request }) => {
  for (const relativePath of seededComponentPaths.splice(0)) {
    const deletion = await request.delete(
      `/component-library/components?user_id=component-ui-smoke&component_id=${encodeURIComponent(relativePath.replace(/^components\//u, ''))}`,
    )
    if (!deletion.ok() && deletion.status() !== 404) throw new Error(`component cleanup failed: ${deletion.status()}`)
  }
})

test('deleting a component removes it without a path-not-found error', async ({ page, request }) => {
  const title = `component-delete-smoke-${Date.now()}`
  const createdResponse = await request.post('/component-library/components', {
    data: {
      user_id: 'component-ui-smoke',
      filename: `${title}.vue`,
      tag: 'buttons',
      source: '<template><button>Delete smoke</button></template>',
    },
  })
  expect(createdResponse.ok()).toBe(true)
  const created = (await createdResponse.json() as { component: { component_id: string } }).component
  seededComponentPaths.push(`components/${created.component_id}`)

  await page.goto('/')
  await page.getByRole('textbox', { name: '用户 ID' }).fill('component-ui-smoke')
  await page.getByRole('button', { name: '进入', exact: true }).click()
  const knowledgeButton = page.getByRole('button', { name: '库', exact: true })
  await expect(knowledgeButton).toBeVisible({ timeout: 20_000 })
  await knowledgeButton.hover()
  await page.getByRole('button', { name: '组件库', exact: true }).click()

  const card = page.getByRole('button', { name: `重命名 ${title}` }).locator('xpath=ancestor::article')
  await expect(card).toBeVisible()
  page.once('dialog', (dialog) => dialog.accept())
  await card.getByRole('button', { name: '删除组件', exact: true }).click()
  await expect(card).toHaveCount(0)

  const listedResponse = await request.get('/component-library/components?user_id=component-ui-smoke&tag=buttons')
  const listed = await listedResponse.json() as { components: Array<{ component_id: string }> }
  expect(listed.components.some((component) => component.component_id === created.component_id)).toBe(false)
})

test('component library masonry, details, and live Vue upload preview work together', async ({ context, page }) => {
  test.setTimeout(90_000)
  const browserOrigin = new URL(process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:5173').origin
  await context.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: browserOrigin })
  const browserErrors: string[] = []
  page.on('pageerror', (error) => browserErrors.push(error.message))
  const runSuffix = Date.now().toString()
  const interactiveTitle = `component-library-smoke-button-${runSuffix}`
  const tallCardTitle = `component-library-smoke-card-${runSuffix}`

  await page.goto('/')
  const userIdInput = page.getByRole('textbox', { name: '用户 ID' })
  await expect(userIdInput).toBeVisible()
  await userIdInput.fill('component-ui-smoke')
  await expect(userIdInput).toHaveValue('component-ui-smoke')
  const enterButton = page.getByRole('button', { name: '进入', exact: true })
  await expect(enterButton).toBeEnabled()
  await enterButton.click()
  const knowledgeButton = page.getByRole('button', { name: '库', exact: true })
  await expect(knowledgeButton).toBeVisible({ timeout: 20_000 })
  await knowledgeButton.hover()
  await expect(knowledgeButton).toHaveAttribute('aria-expanded', 'true')
  await page.getByRole('button', { name: '组件库', exact: true }).click()

  const renameSeedResponse = await page.request.post('/component-library/components', {
    data: {
      user_id: 'component-ui-smoke',
      filename: 'component-library-rename-smoke.vue',
      tag: 'buttons',
      source: '<template><button class="rename-smoke">Rename smoke</button></template>',
    },
  })
  expect(renameSeedResponse.ok()).toBe(true)
  const renameSeed = (await renameSeedResponse.json() as {
    component: { component_id: string; title: string }
  }).component
  const renameSeedPathIndex = seededComponentPaths.push(`components/${renameSeed.component_id}`) - 1

  const fixtures = [
    {
      filename: `component-library-smoke-checkbox-${runSuffix}.vue`,
      tag: 'checkboxes',
      source: '<template><label><input type="checkbox"> Smoke</label></template>',
    },
    {
      filename: `${interactiveTitle}.vue`,
      tag: 'buttons',
      source: '<template><button @click="$event.currentTarget.textContent=\'Done\'">Smoke</button></template>',
    },
    {
      filename: `${tallCardTitle}.html`,
      tag: 'cards',
      source: '<div style="width:180px;height:320px;background:#ddd">Tall smoke card</div>',
    },
  ]
  for (const fixture of fixtures) {
    const response = await page.request.post('/component-library/components', {
      data: { user_id: 'component-ui-smoke', ...fixture },
    })
    const payload = await response.json() as { component: { component_id: string } }
    seededComponentPaths.push(`components/${payload.component.component_id}`)
  }
  await page.getByRole('button', { name: 'buttons', exact: true }).click()
  await page.getByRole('button', { name: 'all', exact: true }).click()

  await expect(page.getByRole('complementary', { name: '组件标签' })).toBeVisible()
  await expect(page.locator('.tag-option')).toHaveCount(11)
  await expect(page.locator('.tag-option').first()).toHaveText('all')
  const toolbar = page.locator('.component-toolbar')
  const uploadButton = toolbar.getByRole('button', { name: '上传组件', exact: true })
  const favoriteFilter = toolbar.getByRole('button', { name: '我的收藏', exact: true })
  await expect(uploadButton).toBeVisible()
  await expect(favoriteFilter).toBeVisible()
  await expect(toolbar.locator('.toolbar-copy span')).toHaveCount(0)
  expect(await toolbar.evaluate((element) => getComputedStyle(element).borderBottomStyle)).toBe('none')
  const tagSidebar = page.locator('.tag-sidebar')
  expect(await tagSidebar.evaluate((element) => ({
    border: getComputedStyle(element).borderStyle,
    shadow: getComputedStyle(element).boxShadow,
    animation: getComputedStyle(element).animationDuration,
  }))).toEqual({ border: 'none', shadow: expect.not.stringMatching(/^none$/u), animation: '0.22s' })
  const tagHoverIndicator = tagSidebar.locator('.tag-hover-indicator')
  await page.getByRole('button', { name: 'buttons', exact: true }).hover()
  await expect(tagHoverIndicator).toHaveCSS('opacity', '1')
  const firstTagTransform = await tagHoverIndicator.evaluate((element) => getComputedStyle(element).transform)
  await page.getByRole('button', { name: 'cards', exact: true }).hover()
  await expect.poll(() => tagHoverIndicator.evaluate((element) => getComputedStyle(element).transform)).not.toBe(firstTagTransform)
  const toolbarBox = await toolbar.boundingBox()
  const uploadBox = await uploadButton.boundingBox()
  expect(uploadBox?.x).toBeGreaterThan((toolbarBox?.x ?? 0) + (toolbarBox?.width ?? 0) / 2)
  expect(uploadBox?.width).toBeGreaterThanOrEqual(116)
  expect(await uploadButton.evaluate((element) => getComputedStyle(element).borderRadius)).toBe('999px')
  expect(await uploadButton.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true)

  await expect.poll(() => page.locator('.component-card').count(), { timeout: 20_000 }).toBeGreaterThanOrEqual(3)
  await expect.poll(async () => {
    const positions = await page.locator('.component-card').evaluateAll((cards) => (
      cards.slice(0, 4).map((card) => Math.round(card.getBoundingClientRect().y))
    ))
    return new Set(positions).size
  }).toBeGreaterThan(1)
  const tallCard = page.getByRole('button', { name: `重命名 ${tallCardTitle}` }).locator('xpath=ancestor::article')
  await expect.poll(async () => tallCard.locator('.preview-surface').evaluate(
    (surface) => Math.round(surface.getBoundingClientRect().height),
  )).toBeGreaterThanOrEqual(280)
  const interactiveCard = page.getByRole('button', { name: `重命名 ${interactiveTitle}` }).locator('xpath=ancestor::article')
  expect(await interactiveCard.frameLocator('iframe').locator('body').evaluate((body) => ({
    display: getComputedStyle(body).display,
    placeItems: getComputedStyle(body).placeItems,
    paddingTop: getComputedStyle(body).paddingTop,
    paddingBottom: getComputedStyle(body).paddingBottom,
  }))).toEqual({ display: 'grid', placeItems: 'center', paddingTop: '32px', paddingBottom: '32px' })

  const interactiveButton = interactiveCard.frameLocator('iframe').getByRole('button', { name: 'Smoke' })
  await interactiveButton.click()
  await expect(interactiveButton).toHaveText('Done')
  await expect(interactiveCard).toBeVisible()
  await expect(interactiveCard.locator('iframe')).toBeVisible()

  const componentFavorite = interactiveCard.getByRole('button', { name: '收藏', exact: true })
  await componentFavorite.click()
  await expect(componentFavorite).toHaveAttribute('aria-pressed', 'true')
  await page.locator('.activity-bar').getByRole('button', { name: '我的收藏', exact: true }).click()
  await page.getByRole('button', { name: '组件', exact: true }).click()
  const favoriteComponentCard = page.getByRole('button', { name: `重命名 ${interactiveTitle}` }).locator('xpath=ancestor::article')
  await expect(favoriteComponentCard).toBeVisible()
  await favoriteComponentCard.getByRole('button', { name: '取消收藏', exact: true }).click()
  await expect(favoriteComponentCard).toHaveCount(0)
  await knowledgeButton.hover()
  await page.getByRole('button', { name: '组件库', exact: true }).click()

  const seededNameTrigger = page.getByRole('button', { name: `重命名 ${renameSeed.title}` })
  await expect(seededNameTrigger).toBeVisible()
  const seededCard = seededNameTrigger.locator('xpath=ancestor::article')
  const seededCardY = (await seededCard.boundingBox())?.y
  await seededCard.hover()
  expect((await seededCard.boundingBox())?.y).toBe(seededCardY)

  const cardRenameTitle = `card-rename-${Date.now()}`
  await seededNameTrigger.click()
  await page.locator('.component-name-input').fill(cardRenameTitle)
  await page.locator('.component-name-input').press('Enter')
  await expect(page.getByRole('button', { name: `重命名 ${cardRenameTitle}` })).toBeVisible()
  let renameList = await page.request.get('/component-library/components?user_id=component-ui-smoke&tag=buttons')
  let renamedItem = (await renameList.json() as {
    components: Array<{ component_id: string; title: string }>
  }).components.find((component) => component.title === cardRenameTitle)
  expect(renamedItem).toBeTruthy()
  seededComponentPaths[renameSeedPathIndex] = `components/${renamedItem?.component_id}`

  const firstCard = page.getByRole('button', { name: `重命名 ${cardRenameTitle}` }).locator('xpath=ancestor::article')
  const firstPreview = firstCard.locator('.preview-surface')
  const detailButton = firstCard.getByRole('button', { name: '查看详情' })
  const copyButton = firstCard.getByRole('button', { name: '复制代码' })
  const firstPreviewBox = await firstPreview.boundingBox()
  const detailButtonBox = await detailButton.boundingBox()
  expect(detailButtonBox?.x).toBeGreaterThan((firstPreviewBox?.x ?? 0) + (firstPreviewBox?.width ?? 0) / 2)
  expect(await detailButton.evaluate((element) => ({
    border: getComputedStyle(element).borderStyle,
    shadow: getComputedStyle(element).boxShadow,
  }))).toEqual({ border: 'none', shadow: 'none' })
  await expect(copyButton).toHaveText('')
  expect(await copyButton.evaluate((element) => getComputedStyle(element).borderStyle)).toBe('none')
  await detailButton.click()
  await expect(page.getByRole('region', { name: '组件详情' })).toBeVisible()
  const detailRenameTitle = `detail-rename-${Date.now()}`
  const detailNameTrigger = toolbar.getByRole('button', { name: `重命名 ${cardRenameTitle}` })
  await detailNameTrigger.click()
  await toolbar.locator('.component-name-input').fill(detailRenameTitle)
  await toolbar.locator('.component-name-input').press('Enter')
  await expect(toolbar.getByRole('button', { name: `重命名 ${detailRenameTitle}` })).toBeVisible()
  renameList = await page.request.get('/component-library/components?user_id=component-ui-smoke&tag=buttons')
  renamedItem = (await renameList.json() as {
    components: Array<{ component_id: string; title: string }>
  }).components.find((component) => component.title === detailRenameTitle)
  expect(renamedItem).toBeTruthy()
  seededComponentPaths[renameSeedPathIndex] = `components/${renamedItem?.component_id}`

  const detailContent = page.locator('.component-content.detail-content')
  const detailWorkbench = page.locator('.detail-workbench')
  expect(await detailContent.evaluate((element) => getComputedStyle(element).padding)).toBe('0px')
  expect(await detailWorkbench.evaluate((element) => ({
    border: getComputedStyle(element).borderStyle,
    radius: getComputedStyle(element).borderRadius,
  }))).toEqual({ border: 'none', radius: '0px' })
  const detailContentBox = await detailContent.boundingBox()
  const detailWorkbenchBox = await detailWorkbench.boundingBox()
  expect(Math.abs((detailWorkbenchBox?.x ?? 0) - (detailContentBox?.x ?? 0))).toBeLessThan(1)
  expect(Math.abs((detailWorkbenchBox?.y ?? 0) - (detailContentBox?.y ?? 0))).toBeLessThan(1)
  expect(Math.abs((detailWorkbenchBox?.width ?? 0) - (detailContentBox?.width ?? 0))).toBeLessThan(1)
  expect(Math.abs((detailWorkbenchBox?.height ?? 0) - (detailContentBox?.height ?? 0))).toBeLessThan(1)
  const detailBack = page.getByRole('button', { name: '返回组件列表' })
  expect(await detailBack.evaluate((element) => ({
    border: getComputedStyle(element).borderStyle,
    background: getComputedStyle(element).backgroundColor,
  }))).toEqual({ border: 'none', background: 'rgba(0, 0, 0, 0)' })
  for (const selector of ['.detail-preview-panel', '.detail-code-panel', '.panel-header', '.detail-copy-button']) {
    expect(await page.locator(selector).first().evaluate((element) => getComputedStyle(element).borderStyle)).toBe('none')
  }
  const detailCopyButton = page.locator('.detail-copy-button')
  await expect(detailCopyButton).toHaveText('')
  expect(await detailCopyButton.evaluate((element) => getComputedStyle(element).backgroundColor)).toBe('rgba(0, 0, 0, 0)')
  const highlightedCode = page.locator('.detail-code-panel .code-preview code')
  await expect(highlightedCode).toContainText('<template>')
  await expect(highlightedCode.locator('.hljs-tag')).not.toHaveCount(0)
  const highlightedCodeStyle = await highlightedCode.evaluate((element) => ({
    family: getComputedStyle(element).fontFamily,
    size: getComputedStyle(element).fontSize,
  }))
  const configuredCodeStyle = await page.locator('html').evaluate((element) => {
    const style = getComputedStyle(element)
    return {
      firstFamily: style.getPropertyValue('--font-code').split(',')[0]?.replace(/["']/gu, '').trim() || '',
      size: 13 * Number(style.getPropertyValue('--font-scale')),
    }
  })
  expect(highlightedCodeStyle.family).toContain(configuredCodeStyle.firstFamily)
  expect(Number.parseFloat(highlightedCodeStyle.size)).toBeCloseTo(configuredCodeStyle.size, 1)
  await expect(page.locator('.detail-preview-panel iframe')).toBeVisible()
  expect(await page.frameLocator('.detail-preview-panel iframe').locator('body').evaluate((body) => ({
    placeItems: getComputedStyle(body).placeItems,
    overflow: getComputedStyle(body).overflow,
  }))).toEqual({ placeItems: 'center', overflow: 'hidden' })
  await page.screenshot({ path: 'test-results/component-library-detail.png', fullPage: true })
  await detailBack.click()

  await page.locator('.component-card').first().getByRole('button', { name: '复制代码' }).click()
  await expect(page.locator('.component-card').first().getByRole('button', { name: '已复制' })).toBeVisible()
  await expect.poll(() => page.evaluate(() => navigator.clipboard.readText())).not.toBe('')
  await page.screenshot({ path: 'test-results/component-library-grid.png', fullPage: true })

  await page.getByRole('button', { name: 'checkboxes', exact: true }).click()
  await expect.poll(() => page.locator('.component-card').count()).toBeGreaterThanOrEqual(1)
  const checkboxFrame = page.frameLocator('.component-card iframe').first()
  const checkbox = checkboxFrame.locator('input[type="checkbox"]')
  await expect(checkbox).not.toBeChecked()
  await checkboxFrame.locator('label').click()
  await expect(checkbox).toBeChecked()
  await expect.poll(async () => page.locator('.component-card .preview-surface').first().evaluate(
    (surface) => Math.round(surface.getBoundingClientRect().height),
  )).toBeLessThan(150)
  expect(await checkboxFrame.locator('body').evaluate((body) => getComputedStyle(body).overflow)).toBe('hidden')

  await uploadButton.click()
  const uploadBackdrop = page.locator('.upload-backdrop')
  const uploadForm = page.locator('.upload-form')
  const codePanel = page.locator('.code-panel')
  const previewPanel = page.locator('.preview-panel')
  const compilerGrid = page.locator('.compiler-grid')
  const nameField = page.locator('.name-field')
  const tagField = page.locator('.tag-field')
  await expect(codePanel).toBeVisible()
  await expect(previewPanel).toBeVisible()
  await expect(uploadBackdrop).toBeVisible()
  await expect(page.locator('.component-grid')).toBeVisible()
  await expect(uploadForm.locator('.form-header p')).toHaveCount(0)
  await expect(uploadForm.locator('.preview-placeholder')).toHaveText('')
  expect(await uploadForm.evaluate((form) => getComputedStyle(form).boxShadow)).not.toBe('none')

  const viewport = page.viewportSize()
  const uploadFormBox = await uploadForm.boundingBox()
  const submitActionsBox = await page.locator('.submit-actions').boundingBox()
  expect(Math.abs((uploadFormBox?.x ?? 0) + (uploadFormBox?.width ?? 0) / 2 - (viewport?.width ?? 0) / 2)).toBeLessThan(2)
  expect(Math.abs((uploadFormBox?.y ?? 0) + (uploadFormBox?.height ?? 0) / 2 - (viewport?.height ?? 0) / 2)).toBeLessThan(2)
  expect((submitActionsBox?.y ?? 0) + (submitActionsBox?.height ?? 0)).toBeLessThanOrEqual(
    (uploadFormBox?.y ?? 0) + (uploadFormBox?.height ?? 0),
  )

  const codeBox = await codePanel.boundingBox()
  const previewBox = await previewPanel.boundingBox()
  const compilerBox = await compilerGrid.boundingBox()
  const nameBox = await nameField.boundingBox()
  const tagBox = await tagField.boundingBox()
  expect(codeBox?.x).toBeLessThan(previewBox?.x ?? 0)
  expect(nameBox?.y).toBeGreaterThanOrEqual((compilerBox?.y ?? 0) + (compilerBox?.height ?? 0))
  expect(nameBox?.y).toBeLessThan(tagBox?.y ?? 0)
  expect(tagBox?.y).toBeGreaterThanOrEqual((compilerBox?.y ?? 0) + (compilerBox?.height ?? 0))
  expect(Math.abs((tagBox?.width ?? 0) - (uploadFormBox?.width ?? 0) / 2)).toBeLessThan(2)
  expect(await page.locator('input[name="component-name"]').evaluate(
    (element) => Number.parseFloat(getComputedStyle(element).paddingLeft),
  )).toBeGreaterThan(14)
  const tagPicker = page.locator('.tag-field .library-tag-picker')
  const tagPickerBox = await tagPicker.boundingBox()
  await tagPicker.getByTitle('选择已有标签').click()
  const tagMenuBox = await page.locator('.ui-dropdown-content').boundingBox()
  expect((tagMenuBox?.x ?? 0) + (tagMenuBox?.width ?? 0)).toBeLessThanOrEqual(
    (uploadFormBox?.x ?? 0) + (uploadFormBox?.width ?? 0) / 2 + 8,
  )
  await page.keyboard.press('Escape')

  const fileInput = page.locator('.hidden-file-input')
  await fileInput.setInputFiles([
    { name: 'one.vue', mimeType: 'text/plain', buffer: Buffer.from('<template><button>One</button></template>') },
    { name: 'two.html', mimeType: 'text/html', buffer: Buffer.from('<button>Two</button>') },
  ])
  const filePicker = page.locator('.file-picker-button')
  await expect(filePicker).toHaveText('')
  await expect(filePicker).toHaveAttribute('title', '已选择 2 个文件')
  const filePickerBox = await filePicker.boundingBox()
  const actionsBox = await page.locator('.form-actions').boundingBox()
  expect(filePickerBox?.x).toBeLessThan((actionsBox?.x ?? 0) + (actionsBox?.width ?? 0) / 2)
  expect(Math.abs((filePickerBox?.x ?? 0) - (tagPickerBox?.x ?? 0))).toBeLessThan(2)

  await page.locator('.code-panel textarea').fill(`
    <script setup>
    import { ref } from 'vue'
    const count = ref(0)
    </script>
    <template><button @click="count += 1">{{ count }}</button></template>
    <style>button { padding: 12px 20px; }</style>
  `)
  const previewButton = page.frameLocator('iframe[title="待上传组件 实时预览"]').getByRole('button')
  await expect(previewButton).toHaveText('0')
  await previewButton.click()
  await expect(previewButton).toHaveText('1')
  await page.screenshot({ path: 'test-results/component-library-upload.png', fullPage: true })

  expect(browserErrors).toEqual([])
})
