/**
 * Resource-manager folder artwork browser smoke test.
 *
 * Usage:
 * Verifies that real medium and large icon views use the animated folder
 * component while files and the small icon view retain their existing icons.
 */
import { expect, test } from '@playwright/test'

test('uses the animated folder component in medium and large icon views', async ({ page }, testInfo) => {
  await page.route('**/*', async (route) => {
    const request = route.request()
    const pathname = new URL(request.url()).pathname
    if (pathname === '/health') {
      await route.fulfill({ status: 200, body: 'ok' })
      return
    }
    if (pathname === '/settings/models/status') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ embedding: 'ready', rerank: 'ready' }),
      })
      return
    }
    if (pathname === '/settings/profile') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          user_id: 'folder-e2e-user',
          knowledge_dir: 'D:/Knowledge',
          active_library_id: 'default',
          knowledge_libraries: [],
        }),
      })
      return
    }
    if (pathname === '/knowledge/files') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          tree: [
            { name: 'Documents', path: 'Documents', isDir: true, children: [] },
            { name: 'readme.md', path: 'readme.md', isDir: false, size: 256 },
          ],
        }),
      })
      return
    }
    const emptyResponses: Record<string, unknown> = {
      '/favorites': { favorites: [] },
      '/knowledge/trash': { entries: [] },
      '/sessions': [],
      '/sessions/observability/history': [],
      '/agent/token-usage': { interval: '5m', calls: [], buckets: [], sessions: [] },
      '/skills': { skills: [], count: 0 },
      '/todo/list': [],
      '/automation/list': [],
      '/library/items': { items: [] },
      '/git/status': {
        initialized: false,
        branches: [],
        remote_branches: [],
        remotes: [],
        changes: [],
        untracked: [],
        ignored: [],
      },
    }
    if (pathname in emptyResponses) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(emptyResponses[pathname]),
      })
      return
    }
    if (request.resourceType() === 'fetch' || request.resourceType() === 'xhr') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' })
      return
    }
    await route.continue()
  })

  await page.addInitScript(() => {
    localStorage.setItem('agent_editor_profile', JSON.stringify({
      userId: 'folder-e2e-user',
      knowledgeDir: 'D:/Knowledge',
      activeLibraryId: 'default',
      knowledgeLibraries: [],
    }))
  })
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto('/')
  await page.getByRole('button', { name: '进入文件', exact: true }).click()

  await page.getByTitle('中图标').click()
  const mediumView = page.locator('.icon-medium')
  await expect(mediumView.locator('.animated-folder-icon.is-medium')).toHaveCount(1)
  await expect(mediumView.locator('.material-file-icon-medium')).toHaveCount(1)

  const folderTile = mediumView.locator('.icon-tile').filter({ hasText: 'Documents' })
  const folderArtwork = folderTile.locator('.animated-folder-icon')
  await folderArtwork.hover()
  await expect.poll(() => folderArtwork.locator('.folder-front').evaluate((element) => {
    return window.getComputedStyle(element).transform
  })).not.toBe('none')
  await folderTile.click()
  await expect(folderTile).toHaveClass(/selected/)
  await expect(folderArtwork).toHaveClass(/is-open/)
  await mediumView.screenshot({ path: testInfo.outputPath('resource-folder-medium.png') })

  await page.getByTitle('大图标').click()
  const largeView = page.locator('.icon-large')
  await expect(largeView.locator('.animated-folder-icon.is-large')).toHaveCount(1)
  await expect(largeView.locator('.material-file-icon-large')).toHaveCount(1)
  await largeView.screenshot({ path: testInfo.outputPath('resource-folder-large.png') })

  await page.getByTitle('小图标').click()
  await expect(page.locator('.icon-small .animated-folder-icon')).toHaveCount(0)
  await expect(page.locator('.icon-small .material-file-icon-small')).toHaveCount(2)
})
