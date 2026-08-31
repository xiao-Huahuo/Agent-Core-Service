/** DSH opt-in setting persistence and responsive basic-settings smoke. */

import { expect, test } from '@playwright/test'

test('keeps DSH disabled by default and persists explicit enablement', async ({ page }) => {
  let dshEnabled = false
  let savedPayload: Record<string, unknown> | null = null
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
      user_id: 'smoke-user', knowledge_dir: 'D:/Knowledge', active_library_id: '',
      knowledge_libraries: [], auto_ingest_on_upload: false, ocr_enabled: false,
      vision_understanding_enabled: false, dsh_coding_agent_enabled: dshEnabled,
      knowledge_ignore_patterns: '', knowledge_supported_suffixes: ['.md', '.pdf'],
      created_at: '2026-08-31T00:00:00Z', updated_at: '2026-08-31T00:00:00Z',
    } })
    if (pathname === '/settings/profile/ingestion' && request.method() === 'PUT') {
      savedPayload = request.postDataJSON() as Record<string, unknown>
      dshEnabled = Boolean(savedPayload.dsh_coding_agent_enabled)
      return route.fulfill({ json: {
        auto_ingest_on_upload: false, ocr_enabled: false, vision_understanding_enabled: false,
        dsh_coding_agent_enabled: dshEnabled, knowledge_ignore_patterns: '', restart_required: false,
      } })
    }
    if (pathname === '/settings/models/initialize') return route.fulfill({ json: { status: 'started' } })
    if (pathname === '/settings/sdks/dsh/initialize') return route.fulfill({ json: { status: 'disabled', enabled: false } })
    return route.fulfill({ json: {} })
  })

  await page.goto('/')
  await page.getByRole('button', { name: 'Settings' }).click()
  const dshRow = page.locator('.toggle-row').filter({ hasText: '启用 DSH coding agent' })
  const toggle = dshRow.locator('input[type="checkbox"]')
  await expect(toggle).not.toBeChecked()
  await toggle.check()
  await expect.poll(() => savedPayload?.dsh_coding_agent_enabled).toBe(true)

  for (const width of [1024, 768, 480]) {
    await page.setViewportSize({ width, height: 820 })
    await expect(dshRow).toBeVisible()
    await expect.poll(() => page.locator('.settings-body').evaluate(element => (
      element.scrollWidth - element.clientWidth
    ))).toBeLessThanOrEqual(1)
    await page.screenshot({ path: `test-results/dsh-basic-setting-${width}.png`, fullPage: true })
  }
})
