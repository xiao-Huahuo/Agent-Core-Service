/**
 * Networking settings integration browser smoke test.
 *
 * Usage:
 * Verifies that the former browser tab migrates to networking settings, keeps
 * both configuration sections usable, and remains contained on narrow screens.
 */
import { expect, test } from '@playwright/test'

test('browser settings are integrated into networking settings', async ({ page }) => {
  const userId = 'web-browser-fusion-smoke'
  let savedBrowserConfig: Record<string, unknown> = {}

  await page.route('**/*', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    if (url.pathname === '/health') {
      await route.fulfill({ status: 200, body: 'ok' })
      return
    }
    if (url.pathname === '/settings/models/status') {
      await route.fulfill({ json: { embedding: 'ready', rerank: 'ready' } })
      return
    }
    if (url.pathname === '/settings/profile') {
      await route.fulfill({ json: {
        user_id: userId,
        knowledge_dir: 'D:/Knowledge',
        active_library_id: 'default',
        knowledge_libraries: [],
      } })
      return
    }
    if (url.pathname === '/settings/web-search/config') {
      if (request.method() === 'PUT') savedBrowserConfig = request.postDataJSON() as Record<string, unknown>
      await route.fulfill({ json: {
        user_id: userId,
        proxy_url: 'http://127.0.0.1:7890',
        browser_proxy_url: String(savedBrowserConfig.browser_proxy_url ?? 'socks5://127.0.0.1:1080'),
        browser_home_url: String(savedBrowserConfig.browser_home_url ?? 'https://example.com'),
        web_search_enabled: true,
        web_search_max_results: 12,
      } })
      return
    }
    if (request.resourceType() === 'fetch' || request.resourceType() === 'xhr') {
      await route.fulfill({ json: {} })
      return
    }
    await route.continue()
  })

  await page.addInitScript(({ profile }) => {
    localStorage.setItem('agent_editor_profile', JSON.stringify(profile))
    localStorage.setItem('agent_editor_settings_active_tab', 'browser')
  }, {
    profile: { userId, knowledgeDir: 'D:/Knowledge', activeLibraryId: 'default', knowledgeLibraries: [] },
  })

  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  await page.getByRole('button', { name: 'Settings' }).click()

  const settingsSidebar = page.locator('.settings-sidebar')
  await expect(settingsSidebar.getByRole('button', { name: '浏览器', exact: true })).toHaveCount(0)
  await expect(settingsSidebar.getByRole('button', { name: '联网配置', exact: true })).toHaveClass(/active/)
  await expect(page.getByRole('heading', { name: '联网搜索' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '内置浏览器' })).toBeVisible()
  await expect(page.locator('#browser-home-url')).toHaveValue('https://example.com')
  await expect(page.locator('#browser-proxy-url')).toHaveValue('socks5://127.0.0.1:1080')

  await page.locator('#browser-home-url').fill('https://openai.com')
  await page.getByRole('button', { name: '保存浏览器配置' }).click()
  await expect.poll(() => savedBrowserConfig).toMatchObject({
    user_id: userId,
    browser_home_url: 'https://openai.com',
    browser_proxy_url: 'socks5://127.0.0.1:1080',
  })
  await expect(page.getByText('已保存', { exact: true })).toBeVisible()
  await expect.poll(() => page.locator('.settings-body').evaluate(
    (settingsBody) => settingsBody.scrollWidth <= settingsBody.clientWidth,
  )).toBe(true)
})
