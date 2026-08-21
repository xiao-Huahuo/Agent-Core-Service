/** Browser smoke tests for state-aware file-tree ingestion and graph actions. */

import { expect, test } from '@playwright/test'

const profile = {
  userId: 'menu-user', knowledgeDir: 'D:/Knowledge', activeLibraryId: 'default', knowledgeLibraries: [],
}

/** Install the minimal workspace API surface and expose captured execution decisions. */
async function mockWorkspace(
  page: import('@playwright/test').Page,
  initial: 'ready' | 'dirty',
  includeDotEntries = false,
) {
  let ingested = initial === 'ready'
  let ingestionPosts = 0
  const graphBodies: Array<Record<string, unknown>> = []
  const job = () => ({
    job_id: 'ingest-menu', user_id: 'menu-user', library_id: 'default', path: 'notes.md', name: 'notes.md',
    pipeline: 'markdown', status: 'finished', stage: 'completed', stage_label: '灌库完成', progress: 100,
    stage_current: 1, stage_total: 1, message: '', error: '', created_at: '2026-08-20T10:00:00Z',
    updated_at: '2026-08-20T10:00:01Z', finished_at: '2026-08-20T10:00:01Z',
  })
  await page.addInitScript((storedProfile) => {
    localStorage.setItem('agent_editor_profile', JSON.stringify(storedProfile))
  }, profile)
  await page.route('**/*', async (route) => {
    const request = route.request()
    if (!['fetch', 'xhr'].includes(request.resourceType())) return route.continue()
    const path = new URL(request.url()).pathname
    if (path === '/health') return route.fulfill({ body: 'ok' })
    if (path === '/settings/models/status') return route.fulfill({ json: { embedding: 'ready', rerank: 'ready' } })
    if (path === '/settings/profile') return route.fulfill({ json: { user_id: 'menu-user', knowledge_dir: 'D:/Knowledge', active_library_id: 'default', knowledge_libraries: [] } })
    if (path === '/knowledge/files') return route.fulfill({ json: { tree: [
      ...(includeDotEntries ? [{
        name: '.git', path: '.git', isDir: true, indexStatus: 'ignored', graphStatus: 'ignored',
        children: [{ name: 'HEAD', path: '.git/HEAD', isDir: false, size: 32, indexStatus: 'ignored', graphStatus: 'ignored' }],
      }, {
        name: '.notes.md', path: '.notes.md', isDir: false, size: 64, indexStatus: 'dirty', graphStatus: 'dirty',
      }] : []),
      {
        name: 'notes.md', path: 'notes.md', isDir: false, size: 128,
        indexStatus: ingested ? 'indexed' : 'dirty', graphStatus: initial === 'ready' ? 'graphed' : 'dirty',
      },
    ] } })
    if (path === '/knowledge/ingestion/jobs' && request.method() === 'POST') {
      ingestionPosts += 1
      ingested = true
      return route.fulfill({ json: { jobs: [job()] } })
    }
    if (path === '/knowledge/ingestion/jobs') return route.fulfill({ json: { jobs: ingested ? [job()] : [] } })
    if (path === '/knowledge/graph/rebuild') {
      graphBodies.push(request.postDataJSON() as Record<string, unknown>)
      return route.fulfill({ json: { status: 'started', message: 'started' } })
    }
    if (path === '/knowledge/graph/rebuild/status') return route.fulfill({ json: {
      status: 'completed', total: 1, current: 1, message: '完成', docs: [],
    } })
    if (path === '/favorites') return route.fulfill({ json: { favorites: [] } })
    if (path === '/privacy') return route.fulfill({ json: { privacy: [] } })
    if (path === '/knowledge/trash') return route.fulfill({ json: { entries: [] } })
    if (path === '/sessions') return route.fulfill({ json: [] })
    if (path === '/agent/children') return route.fulfill({ json: { children: [] } })
    if (path === '/todo/list' || path === '/automation/list') return route.fulfill({ json: [] })
    return route.fulfill({ json: {} })
  })
  return {
    ingestionPosts: () => ingestionPosts,
    graphBodies,
  }
}

test('reuses indexed content and offers explicit re-ingestion and graph re-extraction', async ({ page }) => {
  const calls = await mockWorkspace(page, 'ready')
  await page.goto('/')
  await page.getByRole('button', { name: '进入文件', exact: true }).click()
  await page.locator('.file-item').filter({ hasText: 'notes.md' }).dispatchEvent('contextmenu', { clientX: 320, clientY: 180 })

  const menu = page.locator('.context-menu')
  await expect(menu.getByText('重新灌库文件', { exact: true })).toBeVisible()
  await expect(menu.getByText('重新抽取图谱', { exact: true })).toBeVisible()
  await expect(menu.getByText('在图谱中显示', { exact: true })).toHaveCount(0)
  await menu.locator('button').filter({ hasText: '重新抽取图谱' }).dispatchEvent('click')

  await expect.poll(() => calls.graphBodies.length).toBe(1)
  expect(calls.ingestionPosts()).toBe(0)
  expect(calls.graphBodies[0]).toMatchObject({ path: 'notes.md', force: true })
})

test('ingests a dirty file before starting its first graph extraction', async ({ page }) => {
  const calls = await mockWorkspace(page, 'dirty')
  await page.goto('/')
  await page.getByRole('button', { name: '进入文件', exact: true }).click()
  await page.locator('.file-item').filter({ hasText: 'notes.md' }).dispatchEvent('contextmenu', { clientX: 320, clientY: 180 })
  await page.locator('.context-menu button').filter({ hasText: '抽取图谱' }).dispatchEvent('click')

  await expect.poll(() => calls.ingestionPosts()).toBe(1)
  await expect.poll(() => calls.graphBodies.length).toBe(1)
  expect(calls.graphBodies[0]).toMatchObject({ path: 'notes.md', force: false })
})

test('shows dot directories and their children while keeping them out of ingestion', async ({ page }) => {
  await mockWorkspace(page, 'dirty', true)
  await page.goto('/')
  await page.getByRole('button', { name: 'Files' }).dispatchEvent('click')
  await page.getByRole('button', { name: '刷新文件树' }).dispatchEvent('click')

  const gitDirectory = page.locator('.tree-label').filter({ hasText: '.git' })
  await expect(gitDirectory).toBeVisible()
  await expect(page.getByText('.notes.md', { exact: true })).toBeVisible()
  await gitDirectory.click()
  await expect(page.getByText('HEAD', { exact: true })).toBeVisible()

  await gitDirectory.dispatchEvent('contextmenu', { clientX: 320, clientY: 180 })
  await expect(page.locator('.context-menu button').filter({ hasText: '灌库文件夹' })).toBeDisabled()
})
