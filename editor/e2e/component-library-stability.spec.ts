/**
 * Component-library and vault-sidebar browser regression.
 *
 * Usage:
 * Uploads a Vue component with a viewport-sized absolute SVG, verifies search,
 * sizing, deletion, and the shared rounded-card treatment of the vault sidebar.
 */
import { expect, test } from '@playwright/test'

const seededPaths: string[] = []
const seededTrashIds: string[] = []
const userId = 'component-stability-smoke'

test.afterEach(async ({ request }) => {
  for (const relativePath of seededPaths.splice(0)) {
    const deletion = await request.delete(
      `/knowledge/files?user_id=${encodeURIComponent(userId)}&path=${encodeURIComponent(relativePath)}`,
    )
    if (!deletion.ok()) continue
    const payload = await deletion.json() as { trash_id?: string }
    if (payload.trash_id) seededTrashIds.push(payload.trash_id)
  }
  for (const trashId of seededTrashIds.splice(0)) {
    await request.delete(`/knowledge/files/trash/${encodeURIComponent(trashId)}?user_id=${encodeURIComponent(userId)}`)
  }
})

test('viewport decorations stay bounded and delete actions move the component to trash', async ({ page }) => {
  test.setTimeout(60_000)
  const title = `viewport-stable-${Date.now()}`
  const source = `<style scoped>
    .button-wrap { position: relative; border-radius: 999px; }
    svg { position: absolute; width: 100%; height: 100%; z-index: 0; }
  </style>
  <template>
    <div class="button-wrap"><button><span>Generate</span></button></div>
    <svg xmlns="http://www.w3.org/2000/svg" height="100%" width="100%"><rect height="100%" width="100%" /></svg>
  </template>`
  const createdResponse = await page.request.post('/component-library/components', {
    data: { user_id: userId, filename: `${title}.vue`, tag: 'buttons', source },
  })
  expect(createdResponse.ok()).toBe(true)
  const created = (await createdResponse.json() as {
    component: { component_id: string }
  }).component
  seededPaths.push(`components/${created.component_id}`)

  await page.goto('/')
  const userIdInput = page.getByRole('textbox', { name: '用户 ID' })
  if (await userIdInput.isVisible()) {
    await userIdInput.fill(userId)
    await page.getByRole('button', { name: '进入', exact: true }).click()
  }
  const knowledgeButton = page.getByRole('button', { name: '库', exact: true })
  await knowledgeButton.hover()
  await expect(knowledgeButton).toHaveAttribute('aria-expanded', 'true')
  await page.getByRole('button', { name: '组件库', exact: true }).click()
  await page.getByRole('button', { name: 'buttons', exact: true }).click()

  const card = page.getByRole('button', { name: `重命名 ${title}` }).locator('xpath=ancestor::article')
  await expect(card).toBeVisible()
  const componentSearch = page.getByRole('searchbox', { name: '搜索组件' })
  await componentSearch.fill(title.slice(0, 12))
  await expect(card).toBeVisible()
  await componentSearch.fill('missing-component-result')
  await expect(page.getByText('没有匹配的组件', { exact: true })).toBeVisible()
  await componentSearch.clear()
  await expect(card).toBeVisible()
  await card.getByRole('button', { name: `重命名 ${title}` }).click()
  const cardNameInput = page.locator('.component-card .component-name-input')
  await expect(cardNameInput).toBeVisible()
  expect(await cardNameInput.evaluate((element) => getComputedStyle(element).boxShadow)).toBe('none')
  await cardNameInput.press('Escape')
  const preview = card.locator('.preview-surface')
  await page.waitForTimeout(1000)
  const firstHeight = await preview.evaluate((element) => Number.parseFloat(getComputedStyle(element).height))
  await page.waitForTimeout(700)
  const secondHeight = await preview.evaluate((element) => Number.parseFloat(getComputedStyle(element).height))
  expect(Math.abs(secondHeight - firstHeight)).toBeLessThan(1)
  expect(secondHeight).toBeLessThan(400)

  const cardDelete = card.getByRole('button', { name: '删除组件' })
  const cardBox = await card.boundingBox()
  const cardDeleteBox = await cardDelete.boundingBox()
  expect(cardDeleteBox?.x).toBeGreaterThan((cardBox?.x ?? 0) + (cardBox?.width ?? 0) / 2)
  expect(cardDeleteBox?.y).toBeGreaterThan((cardBox?.y ?? 0) + (cardBox?.height ?? 0) / 2)

  await card.getByRole('button', { name: '查看详情' }).click()
  const codePanel = page.locator('.detail-code-panel')
  await expect(codePanel).toBeVisible()
  await page.getByRole('button', { name: `重命名 ${title}` }).click()
  const detailNameInput = page.locator('.component-toolbar').getByRole('textbox', { name: '组件名' })
  await expect(detailNameInput).toBeVisible()
  expect(await detailNameInput.evaluate((element) => getComputedStyle(element).boxShadow)).toBe('none')
  await detailNameInput.press('Escape')
  const backgrounds = await page.locator('.component-library-view').evaluate((view) => ({
    page: getComputedStyle(view).backgroundColor,
    code: getComputedStyle(document.querySelector('.detail-code-panel') as Element).backgroundColor,
  }))
  expect(backgrounds.code).toBe(backgrounds.page)

  const detailDelete = page.locator('.detail-delete-button')
  const codePanelBox = await codePanel.boundingBox()
  const detailDeleteBox = await detailDelete.boundingBox()
  expect(detailDeleteBox?.x).toBeGreaterThan((codePanelBox?.x ?? 0) + (codePanelBox?.width ?? 0) / 2)
  expect(detailDeleteBox?.y).toBeLessThan((codePanelBox?.y ?? 0) + 50)

  page.once('dialog', (dialog) => dialog.accept())
  const deletionResponse = page.waitForResponse((response) => (
    response.request().method() === 'DELETE' && response.url().includes('/knowledge/files?')
  ))
  await detailDelete.click()
  const deletion = await deletionResponse
  expect(deletion.ok()).toBe(true)
  const deletionPayload = await deletion.json() as { trash_id?: string }
  if (deletionPayload.trash_id) seededTrashIds.push(deletionPayload.trash_id)
  seededPaths.length = 0

  await expect(page.getByRole('region', { name: '组件详情' })).toHaveCount(0)
  const listed = await page.request.get(`/component-library/components?user_id=${encodeURIComponent(userId)}&tag=buttons`)
  const listedPayload = await listed.json() as { components: Array<{ component_id: string }> }
  expect(listedPayload.components.some((item) => item.component_id === created.component_id)).toBe(false)

  await page.getByRole('button', { name: '上传组件', exact: true }).click()
  await expect(page.locator('input[name="component-name"]')).not.toHaveAttribute('placeholder')
})

test('vault filter sidebar uses the rounded shadow card shell without changing its controls', async ({ page }) => {
  await page.route('**/vault/status**', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ user_id: userId, configured: true, item_count: 0 }),
    })
  })
  await page.route('**/vault/items**', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        items: [],
        total: 0,
        type_counts: { login: 0, card: 0, identity: 0, secure_note: 0 },
      }),
    })
  })
  await page.route('**/vault/tags**', async (route) => {
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ tags: [] }) })
  })
  await page.addInitScript(({ key, value }) => {
    sessionStorage.setItem(key, value)
  }, {
    key: `metaweave_vault_token_${userId}`,
    value: JSON.stringify({ token: 'vault-sidebar-smoke-token', expires_at: '2099-01-01T00:00:00Z' }),
  })

  await page.goto('/')
  const userIdInput = page.getByRole('textbox', { name: '用户 ID' })
  if (await userIdInput.isVisible()) {
    await userIdInput.fill(userId)
    await page.getByRole('button', { name: '进入', exact: true }).click()
  }
  const knowledgeButton = page.getByRole('button', { name: '库', exact: true })
  await knowledgeButton.hover()
  await page.getByRole('button', { name: '密码库', exact: true }).click()

  const filterPanel = page.locator('.filter-panel')
  await expect(filterPanel).toBeVisible()
  const shell = await filterPanel.evaluate((element) => {
    const style = getComputedStyle(element)
    return {
      borderRadius: style.borderRadius,
      borderTopWidth: style.borderTopWidth,
      boxShadow: style.boxShadow,
      marginTop: style.marginTop,
    }
  })
  expect(shell).toMatchObject({ borderRadius: '18px', borderTopWidth: '0px', marginTop: '12px' })
  expect(shell.boxShadow).not.toBe('none')
  await expect(filterPanel.getByRole('searchbox')).toHaveAttribute('placeholder', '搜索密码库')
  await expect(filterPanel.getByRole('button', { name: /全部项目/u })).toBeVisible()
})
