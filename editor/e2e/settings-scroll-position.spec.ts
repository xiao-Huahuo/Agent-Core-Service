/** UI smoke test for settings-tab scroll positioning. */

import { expect, test } from '@playwright/test'

test('keeps short settings pages aligned to the top', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('agent_editor_profile', JSON.stringify({
      userId: 'smoke-user',
      knowledgeDir: 'D:/Knowledge',
      knowledgeLibraries: [],
      knowledgeWatchEnabled: true,
    }))
    localStorage.setItem('agent_editor_settings_active_tab', 'basic')
  })
  await page.route('**/*', async (route) => {
    const request = route.request()
    if (request.resourceType() !== 'fetch' && request.resourceType() !== 'xhr') {
      await route.continue()
      return
    }
    const pathname = new URL(request.url()).pathname
    if (pathname === '/health') {
      await route.fulfill({ json: { ok: true } })
      return
    }
    if (pathname === '/settings/models/status') {
      await route.fulfill({ json: { embedding: 'ready', rerank: 'ready' } })
      return
    }
    if (pathname === '/settings/profile') {
      await route.fulfill({ json: {
        user_id: 'smoke-user',
        knowledge_dir: 'D:/Knowledge',
        knowledge_libraries: [],
        created_at: '2026-08-20T00:00:00Z',
        updated_at: '2026-08-20T00:00:00Z',
      } })
      return
    }
    await route.fulfill({ json: {} })
  })

  await page.goto('/')
  await page.getByRole('button', { name: 'Settings' }).click()

  const settingsBody = page.locator('.settings-body')
  await expect(settingsBody).toBeVisible()
  await page.getByRole('button', { name: '图谱', exact: true }).click()

  await page.waitForTimeout(350)
  const section = page.locator('.setting-section')
  await expect.poll(async () => {
    const bodyBox = await settingsBody.boundingBox()
    const sectionBox = await section.boundingBox()
    return bodyBox && sectionBox ? sectionBox.y - bodyBox.y : Number.POSITIVE_INFINITY
  }).toBeLessThan(40)

  await page.getByRole('button', { name: '外观', exact: true }).click()
  await page.waitForTimeout(350)
  const fontSizeControl = page.locator('.font-size-control[data-font-size="ui"]')
  await expect.poll(() => fontSizeControl.evaluate((element) => {
    const labelBox = element.querySelector('.font-family-header')?.getBoundingClientRect()
    const controlBox = element.querySelector('.font-size-row')?.getBoundingClientRect()
    return labelBox && controlBox ? controlBox.left - labelBox.right : Number.POSITIVE_INFINITY
  })).toBeLessThan(40)
})
