/**
 * Blocked file-type settings browser regression.
 *
 * Usage:
 * Opens the real basic settings page, verifies the effective supported suffix
 * capsules, and confirms that one click persists one unique ignore rule.
 */
import { expect, test } from '@playwright/test'

const supportedSuffixes = [
  '.md', '.txt', '.json', '.jsonl', '.csv', '.tsv', '.html', '.htm', '.xml',
  '.docx', '.xlsx', '.pptx', '.pdf', '.jpg', '.jpeg', '.png', '.webp', '.gif', '.svg',
]

test('supported file type capsules append a unique blocked rule', async ({ page }) => {
  const userId = 'blocked-type-smoke'
  let savedPatterns = ''
  let saveCount = 0

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
        body: JSON.stringify({
          user_id: userId,
          knowledge_dir: 'D:/Knowledge',
          active_library_id: 'default',
          knowledge_libraries: [],
          knowledge_ignore_patterns: '',
          knowledge_supported_suffixes: supportedSuffixes,
        }),
      })
      return
    }
    if (request.method() === 'PUT' && url.pathname === '/settings/profile/ingestion') {
      const payload = request.postDataJSON() as { knowledge_ignore_patterns: string }
      savedPatterns = payload.knowledge_ignore_patterns
      saveCount += 1
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ auto_ingest_on_upload: false, ocr_enabled: false, knowledge_ignore_patterns: savedPatterns }),
      })
      return
    }
    if (request.resourceType() === 'fetch' || request.resourceType() === 'xhr') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' })
      return
    }
    await route.continue()
  })

  await page.addInitScript(({ profile }) => {
    localStorage.setItem('agent_editor_profile', JSON.stringify(profile))
    localStorage.setItem('agent_editor_settings_active_tab', 'basic')
  }, {
    profile: { userId, knowledgeDir: 'D:/Knowledge', activeLibraryId: 'default', knowledgeLibraries: [] },
  })

  await page.goto('/')
  await page.getByRole('button', { name: 'Settings' }).click()

  const ignoreArea = page.locator('.ignore-row')
  const typeArea = page.locator('.blocked-file-types-row')
  await expect(ignoreArea).toBeVisible()
  await expect(typeArea).toBeVisible()
  expect(await typeArea.evaluate((types) => {
    const ignore = document.querySelector('.ignore-row')
    return Boolean((ignore?.compareDocumentPosition(types) ?? 0) & Node.DOCUMENT_POSITION_FOLLOWING)
  })).toBe(true)

  const chips = page.locator('.file-type-chip')
  await expect(chips).toHaveCount(supportedSuffixes.length)
  await expect(chips).toHaveText(supportedSuffixes)

  const pdfChip = page.getByRole('button', { name: '.pdf', exact: true })
  await pdfChip.click()
  await expect(page.locator('.ignore-row textarea')).toHaveValue('*.pdf')
  await expect(pdfChip).toBeDisabled()
  expect(savedPatterns).toBe('*.pdf')
  expect(saveCount).toBe(1)
})
