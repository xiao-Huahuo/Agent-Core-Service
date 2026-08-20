/**
 * Ordinary-table browser regression.
 *
 * Usage:
 * Opens the real smart-forms page, verifies uninterrupted keyboard entry in the
 * creation dialog, then checks ordinary-table defaults and disabled menu states.
 */
import { expect, test } from '@playwright/test'

test('ordinary table starts 10 by 10 without a sequence column and grays disabled menu actions', async ({ page }) => {
  const userId = 'plain-form-smoke'

  await page.route('**/*', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    if (url.pathname === '/health') {
      await route.fulfill({ status: 200, body: 'ok' })
      return
    }
    if (url.pathname === '/settings/models/status') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ embedding: 'ready', rerank: 'ready' }),
      })
      return
    }
    if (url.pathname === '/settings/profile') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ user_id: userId, knowledge_dir: 'D:/Knowledge', active_library_id: 'default', knowledge_libraries: [] }),
      })
      return
    }
    if (request.method() === 'GET' && url.pathname === '/smart-forms/list') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
      return
    }
    if (request.method() === 'POST' && url.pathname === '/knowledge/files/folder') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' })
      return
    }
    if (request.method() === 'POST' && url.pathname === '/smart-forms/save') {
      const payload = request.postDataJSON() as { asset_dir: string; form: Record<string, unknown> }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          form_id: 'sf_plain_smoke',
          user_id: userId,
          asset_dir: payload.asset_dir,
          form: payload.form,
          updated_at: new Date().toISOString(),
        }),
      })
      return
    }
    if (request.method() === 'DELETE' && url.pathname === '/smart-forms/sf_plain_smoke') {
      await route.fulfill({ status: 204, body: '' })
      return
    }
    await route.continue()
  })

  await page.addInitScript(({ profile }) => {
    localStorage.setItem('agent_editor_profile', JSON.stringify(profile))
  }, {
    profile: { userId, knowledgeDir: 'D:/Knowledge', activeLibraryId: 'default', knowledgeLibraries: [] },
  })

  await page.goto('/')
  await page.getByRole('button', { name: '库', exact: true }).hover()
  await page.getByRole('button', { name: '智能表格' }).click()
  await page.getByRole('button', { name: '新建表格' }).click()
  const tableNameInput = page.getByPlaceholder('例如：项目文献库')
  await expect(tableNameInput).toBeFocused()
  await page.locator('button[data-form-kind="plain"]').click()
  await expect(tableNameInput).toBeFocused()
  await page.keyboard.type('普通表格冒烟')
  await expect(tableNameInput).toHaveValue('普通表格冒烟')
  await page.getByRole('button', { name: '创建表格', exact: true }).click()

  await expect(page.locator('.table-frame.plain-table')).toBeVisible()
  await expect(page.getByRole('button', { name: '新建表格', exact: true })).toHaveCSS('border-radius', '999px')
  await expect(page.locator('.smart-table thead th[data-column-id]')).toHaveCount(10)
  await expect(page.locator('.smart-table tbody tr')).toHaveCount(10)
  await expect(page.getByText('序号', { exact: true })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '全表智能填充' })).toHaveCount(0)

  await page.locator('.smart-table tbody tr').first().click({ button: 'right' })
  const disabledMainAction = page.getByRole('button', { name: '智能填充', exact: true })
  await expect(disabledMainAction).toBeDisabled()
  await expect(disabledMainAction).toHaveCSS('cursor', 'not-allowed')

  await page.getByRole('button', { name: '添加列', exact: true }).hover()
  await page.getByRole('button', { name: '左侧添加', exact: true }).hover()
  const disabledNestedAction = page.getByRole('button', { name: '智能文本', exact: true })
  const enabledNestedAction = page.getByRole('button', { name: '文本', exact: true })
  await expect(disabledNestedAction).toBeDisabled()
  await expect(disabledNestedAction).toHaveCSS('cursor', 'not-allowed')
  expect(await disabledNestedAction.evaluate((element) => getComputedStyle(element).color))
    .not.toBe(await enabledNestedAction.evaluate((element) => getComputedStyle(element).color))

  await page.locator('.forms-header h1').click()
  page.once('dialog', (dialog) => dialog.accept())
  await page.getByRole('button', { name: '删除表格', exact: true }).click()
  await expect(page.locator('.form-empty-state')).toContainText('还没有表格')
})
