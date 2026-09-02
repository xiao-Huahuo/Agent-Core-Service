/** Responsive UI smoke coverage for persisted model-capacity settings. */

import { expect, test, type Page } from '@playwright/test'

const VIEWPORTS = [
  { name: 'desktop', width: 1280, height: 900, stacked: false },
  { name: 'tablet', width: 768, height: 900, stacked: false },
  { name: 'mobile', width: 480, height: 900, stacked: true },
] as const

/** Install the minimum backend contract needed to render the real settings page. */
async function mockSettingsBackend(page: Page) {
  await page.addInitScript(() => {
    localStorage.setItem('agent_editor_profile', JSON.stringify({
      userId: 'context-smoke-user',
      knowledgeDir: 'D:/Knowledge',
      knowledgeLibraries: [],
      knowledgeWatchEnabled: true,
    }))
    localStorage.setItem('agent_editor_settings_active_tab', 'llm')
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
    if (pathname === '/settings/profile') {
      await route.fulfill({ json: {
        user_id: 'context-smoke-user',
        knowledge_dir: 'D:/Knowledge',
        knowledge_libraries: [],
        created_at: '2026-08-31T00:00:00Z',
        updated_at: '2026-08-31T00:00:00Z',
      } })
      return
    }
    if (pathname === '/settings/llm/config') {
      await route.fulfill({ json: {
        user_id: 'context-smoke-user',
        model_name: 'main-model',
        base_url: 'https://example.invalid/v1',
        api_key: '',
        small_model_name: 'small-model',
        small_base_url: 'https://example.invalid/v1',
        small_api_key: '',
        model_context_window_tokens: 1_000_000,
        model_max_output_tokens: 65_536,
        small_model_context_window_tokens: 1_000_000,
        small_model_max_output_tokens: 8_192,
        effective_model_name: 'main-model',
        effective_model_source: 'remote',
        effective_small_model_name: 'small-model',
        effective_small_model_source: 'remote',
        updated_at: '2026-08-31T00:00:00Z',
      } })
      return
    }
    if (pathname === '/settings/llm/saved-configs') {
      await route.fulfill({ json: { configs: [] } })
      return
    }
    await route.fulfill({ json: {} })
  })
}

for (const viewport of VIEWPORTS) {
  test(`renders model capacity inputs at ${viewport.name} width`, async ({ page }) => {
    await page.setViewportSize({ width: viewport.width, height: viewport.height })
    await mockSettingsBackend(page)
    await page.goto('/')
    await page.getByRole('button', { name: 'Settings' }).click()

    const contextInputs = page.getByPlaceholder('上下文窗口 token（默认 1000000）')
    const outputInputs = page.getByPlaceholder('最大输出 token（0=继承）')
    await expect(contextInputs).toHaveCount(2)
    await expect(outputInputs).toHaveCount(2)
    await expect(contextInputs.first()).toHaveValue('1000000')
    await expect(contextInputs.last()).toHaveValue('1000000')
    await expect(outputInputs.last()).toHaveValue('8192')

    const contextBox = await contextInputs.first().boundingBox()
    const outputBox = await outputInputs.first().boundingBox()
    expect(contextBox).not.toBeNull()
    expect(outputBox).not.toBeNull()
    if (viewport.stacked) {
      expect(Math.abs((contextBox?.x ?? 0) - (outputBox?.x ?? 0))).toBeLessThan(3)
      expect((outputBox?.y ?? 0) - (contextBox?.y ?? 0)).toBeGreaterThan(20)
    } else {
      expect((outputBox?.x ?? 0) - (contextBox?.x ?? 0)).toBeGreaterThan(100)
      expect(Math.abs((contextBox?.y ?? 0) - (outputBox?.y ?? 0))).toBeLessThan(3)
    }

    await page.screenshot({
      path: `../docs/acceptance/dynamic-context-settings-${viewport.name}.png`,
      fullPage: false,
    })
  })
}

test('retires a persisted 128K fallback meter on the Agent page', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('agent_editor_profile', JSON.stringify({
      userId: 'context-smoke-user',
      knowledgeDir: 'D:/Knowledge',
      knowledgeLibraries: [],
      knowledgeWatchEnabled: true,
    }))
  })
  await page.route('**/*', async (route) => {
    const request = route.request()
    if (request.resourceType() !== 'fetch' && request.resourceType() !== 'xhr') {
      await route.continue()
      return
    }
    const pathname = new URL(request.url()).pathname
    if (pathname === '/settings/llm/config') {
      await route.fulfill({ json: {
        user_id: 'context-smoke-user',
        model_name: 'deepseek-v4-flash',
        effective_model_name: 'deepseek-v4-flash',
        effective_model_source: 'remote',
        context_window_tokens: 1_000_000,
        model_context_window_tokens: 1_000_000,
        small_model_context_window_tokens: 1_000_000,
        updated_at: '2026-09-01T00:00:00Z',
      } })
      return
    }
    if (pathname === '/sessions') {
      await route.fulfill({ json: [{
        session_id: 'sess-legacy-capacity',
        user_id: 'context-smoke-user',
        session_name: '旧12万会话',
        created_at: '2026-09-01T00:00:00Z',
        updated_at: '2026-09-01T00:00:00Z',
      }] })
      return
    }
    if (pathname === '/sessions/sess-legacy-capacity/messages') {
      await route.fulfill({ json: [] })
      return
    }
    if (pathname === '/sessions/sess-legacy-capacity/state') {
      await route.fulfill({ json: { session_state: { context_usage: {
        current_tokens: 80_000,
        max_context_tokens: 120_258,
        trigger_tokens: 96_206,
        target_tokens: 54_116,
        capacity_source: 'conservative_fallback',
      } } } })
      return
    }
    if (pathname === '/health') {
      await route.fulfill({ json: { ok: true } })
      return
    }
    if (pathname === '/settings/profile') {
      await route.fulfill({ json: {
        user_id: 'context-smoke-user',
        knowledge_dir: 'D:/Knowledge',
        knowledge_libraries: [],
      } })
      return
    }
    await route.fulfill({ json: {} })
  })

  await page.goto('/')
  await page.getByRole('button', { name: 'Agent', exact: true }).click()
  await page.getByTitle('Toggle sidebar').click()
  await page.getByText('旧12万会话', { exact: true }).click()

  await expect(page.locator('.context-progress')).toHaveAttribute(
    'title',
    '80,000 / 1,000,000 tokens',
  )
})
