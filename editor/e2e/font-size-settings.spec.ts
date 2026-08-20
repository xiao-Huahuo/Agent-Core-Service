/** UI smoke test for independent UI and editor-text font-size controls. */

import { expect, test } from '@playwright/test'

test('adjusts UI and editor text font sizes independently', async ({ page }) => {
  const savedFontSizes = { ui: 100, text: 100 }
  const profile = {
    userId: 'smoke-user',
    knowledgeDir: 'D:/Knowledge',
    knowledgeLibraries: [],
    knowledgeWatchEnabled: true,
    uiFontFamilies: [],
    textFontFamilies: [],
    uiFontSizePercent: 100,
    textFontSizePercent: 100,
  }
  await page.addInitScript((storedProfile) => {
    localStorage.setItem('agent_editor_profile', JSON.stringify(storedProfile))
    localStorage.setItem('agent_editor_settings_active_tab', 'appearance')
  }, profile)

  await page.route('**/*', async (route) => {
    const request = route.request()
    if (request.resourceType() !== 'fetch' && request.resourceType() !== 'xhr') {
      await route.continue()
      return
    }
    const url = new URL(request.url())
    if (url.pathname === '/health') {
      await route.fulfill({ json: { ok: true } })
      return
    }
    if (url.pathname === '/settings/models/status') {
      await route.fulfill({ json: { embedding: 'ready', rerank: 'ready' } })
      return
    }
    if (url.pathname === '/settings/profile') {
      await route.fulfill({ json: {
        user_id: 'smoke-user',
        knowledge_dir: 'D:/Knowledge',
        knowledge_libraries: [],
        ui_font_families: [],
        text_font_families: [],
        ui_font_size_percent: 100,
        text_font_size_percent: 100,
        created_at: '2026-08-20T00:00:00Z',
        updated_at: '2026-08-20T00:00:00Z',
      } })
      return
    }
    if (url.pathname === '/settings/appearance/font') {
      const body = request.postDataJSON() as Record<string, unknown>
      if (typeof body.ui_font_size_percent === 'number') savedFontSizes.ui = body.ui_font_size_percent
      if (typeof body.text_font_size_percent === 'number') savedFontSizes.text = body.text_font_size_percent
      await route.fulfill({ json: {
        user_id: 'smoke-user',
        ui_font_families: [],
        text_font_families: [],
        ui_font_size_percent: savedFontSizes.ui,
        text_font_size_percent: savedFontSizes.text,
        updated_at: '2026-08-20T00:00:00Z',
      } })
      return
    }
    await route.fulfill({ json: {} })
  })

  await page.goto('/')
  await page.getByRole('button', { name: 'Settings' }).click()

  const uiSize = page.getByRole('slider', { name: 'UI 字体大小' })
  const textSize = page.getByRole('slider', { name: '正文字体大小' })
  await expect(uiSize).toBeVisible()
  await expect(textSize).toBeVisible()

  await page.getByRole('spinbutton', { name: 'UI 字体大小百分比' }).fill('80')
  await expect.poll(() => page.evaluate(() => ({
    ui: document.documentElement.style.getPropertyValue('--font-scale'),
    text: document.documentElement.style.getPropertyValue('--text-font-scale'),
  }))).toEqual({ ui: '0.96', text: '1.56' })

  await page.getByRole('spinbutton', { name: '正文字体大小百分比' }).fill('130')
  await expect.poll(() => page.evaluate(() => ({
    ui: document.documentElement.style.getPropertyValue('--font-scale'),
    text: document.documentElement.style.getPropertyValue('--text-font-scale'),
  }))).toEqual({ ui: '0.96', text: '2.028' })
})
