/** DSH SDK storage card and responsive layout browser smoke. */

import { expect, test } from '@playwright/test'

test('shows real DSH SDK management state without horizontal clipping', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('agent_editor_profile', JSON.stringify({
      userId: 'smoke-user', knowledgeDir: 'D:/Knowledge', knowledgeLibraries: [], knowledgeWatchEnabled: true,
    }))
  })
  await page.route('**/*', async (route) => {
    const request = route.request()
    if (!['fetch', 'xhr'].includes(request.resourceType())) return route.continue()
    const pathname = new URL(request.url()).pathname
    if (pathname === '/health') return route.fulfill({ json: { ok: true } })
    if (pathname === '/settings/profile') return route.fulfill({ json: {
      user_id: 'smoke-user', knowledge_dir: 'D:/Knowledge', knowledge_libraries: [],
      created_at: '2026-08-31T00:00:00Z', updated_at: '2026-08-31T00:00:00Z',
    } })
    if (pathname === '/settings/storage/config') return route.fulfill({ json: {
      paths: [], knowledge_dir_total_bytes: 0, runtime_total_bytes: 192_256_620,
      managed_resource_distribution: [{ name: 'sdks', size_bytes: 192_256_620 }],
    } })
    if (pathname === '/settings/models/management') return route.fulfill({ json: { models: [] } })
    if (pathname === '/settings/latex/management') return route.fulfill({ json: {
      status: 'missing', stage: '', progress: null, message: '未安装', source: 'none', managed: false,
      runtime_path: 'D:/runtime/latex', distribution_path: '', size_bytes: 0, file_count: 0, engines: [], paths: {},
    } })
    if (pathname === '/settings/sdks/dsh/management') return route.fulfill({ json: {
      key: 'deepseek_harness', label: 'DeepSeek Harness SDK', role: '代码子 Agent 与只读执行轨迹',
      version: '0.1.0-rc.5+mw.1', platform: 'Windows x64', path: 'D:/runtime/assets/sdks/dsh',
      size_bytes: 192_256_620, package_size_bytes: 66_008_168, file_count: 1200,
      installed: true, configured: true, in_use: false,
      status: 'ready', message: '可用', processed_bytes: 0, total_bytes: 0, progress: null,
    } })
    return route.fulfill({ json: {} })
  })

  await page.goto('/')
  await page.getByRole('button', { name: 'Settings' }).click()
  await page.getByRole('button', { name: '存储管理', exact: true }).click()
  await expect(page.getByText('DeepSeek Harness SDK', { exact: true })).toBeVisible()
  await expect(page.getByText('0.1.0-rc.5+mw.1', { exact: true })).toBeVisible()
  await expect(page.getByLabel('SDK 与运行组件').getByText('183.4 MB', { exact: true })).toBeVisible()

  for (const width of [1024, 768, 480]) {
    await page.setViewportSize({ width, height: 820 })
    await expect.poll(() => page.locator('.settings-body').evaluate(element => (
      element.scrollWidth - element.clientWidth
    ))).toBeLessThanOrEqual(1)
    await page.screenshot({ path: `test-results/dsh-sdk-storage-${width}.png`, fullPage: true })
  }
})
