import { test, expect } from '@playwright/test'

test('enabling OCR in settings sends the user-level ingestion setting', async ({ page }) => {
  await page.route('**/*', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    if (url.pathname === '/health') {
      await route.fulfill({ status: 200, body: 'ok' })
      return
    }
    if (url.pathname === '/settings/models/status') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ embedding: 'ready', rerank: 'ready', paddleocr: 'ready' }) })
      return
    }
    if (request.method() === 'PUT' && url.pathname === '/settings/profile/ingestion') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ auto_ingest_on_upload: false, ocr_enabled: true, knowledge_ignore_patterns: '' }) })
      return
    }
    if (request.method() === 'GET' && url.pathname === '/settings/profile/ingestion') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ auto_ingest_on_upload: false, ocr_enabled: false, knowledge_ignore_patterns: '' }) })
      return
    }
    if (url.pathname === '/settings/profile') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ user_id: 'e2e-user', knowledge_dir: 'D:/Knowledge', active_library_id: 'default', knowledge_libraries: [{ library_id: 'default', name: 'Default', knowledge_dir: 'D:/Knowledge', is_active: true }], ocr_enabled: false }),
      })
      return
    }
    if (url.pathname.startsWith('/api/')) {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' })
      return
    }
    await route.continue()
  })

  await page.addInitScript(() => {
    localStorage.setItem('agent_editor_profile', JSON.stringify({ userId: 'e2e-user', knowledgeDir: 'D:/Knowledge', activeLibraryId: 'default', knowledgeLibraries: [{ libraryId: 'default', name: 'Default', knowledgeDir: 'D:/Knowledge', isActive: true }] }))
  })
  await page.goto('/')
  await page.getByRole('button', { name: 'Settings' }).click()
  await expect(page.getByRole('heading', { name: '知识库' })).toBeVisible()

  const ocrToggle = page.locator('.toggle-row').filter({ hasText: 'OCR' }).locator('input[type="checkbox"]')
  await expect(ocrToggle).toBeVisible()
  const requestPromise = page.waitForRequest((request) => request.method() === 'PUT' && request.url().includes('/settings/profile/ingestion'))
  await ocrToggle.check()
  const request = await requestPromise
  expect(request.postDataJSON()).toMatchObject({ user_id: 'e2e-user', ocr_enabled: true })
})
