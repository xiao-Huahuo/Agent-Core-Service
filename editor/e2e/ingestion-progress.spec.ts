/** Real-page smoke test for detailed single-file ingestion progress and cancellation. */

import { expect, test } from '@playwright/test'

test('shows per-pipeline details and moves a cancelled file to un-ingested history', async ({ page }, testInfo) => {
  let pdfCancelled = false
  const now = '2026-08-20T10:00:00Z'
  const jobs = () => [
    {
      job_id: 'ingest_pdf', user_id: 'smoke-user', library_id: 'kb1', path: 'paper.pdf', name: 'paper.pdf',
      pipeline: 'pdf', status: pdfCancelled ? 'cancelled' : 'running', stage: pdfCancelled ? 'cancelled' : 'ocr_pages',
      stage_label: pdfCancelled ? '已中止' : '正在 OCR 扫描页', progress: pdfCancelled ? 0 : 64,
      stage_current: pdfCancelled ? 0 : 8, stage_total: pdfCancelled ? 0 : 20, size: 4096, mtime: now,
      message: pdfCancelled ? '用户中止灌库' : '已识别第 8 / 20 页', error: '', created_at: now,
      started_at: now, finished_at: pdfCancelled ? now : null, updated_at: now,
    },
    {
      job_id: 'ingest_xlsx', user_id: 'smoke-user', library_id: 'kb1', path: 'table.xlsx', name: 'table.xlsx',
      pipeline: 'spreadsheet', status: 'running', stage: 'spreadsheet_sheets', stage_label: '正在解析工作表',
      progress: 31, stage_current: 2, stage_total: 5, size: 2048, mtime: now, message: '工作表 2 / 5', error: '',
      created_at: now, started_at: now, finished_at: null, updated_at: now,
    },
    {
      job_id: 'ingest_md', user_id: 'smoke-user', library_id: 'kb1', path: 'notes.md', name: 'notes.md',
      pipeline: 'markdown', status: 'running', stage: 'parse_sections', stage_label: 'Markdown 标题解析完成，共 6 个章节',
      progress: 42, stage_current: 6, stage_total: 6, size: 1024, mtime: now, message: '', error: '',
      created_at: now, started_at: now, finished_at: null, updated_at: now,
    },
  ]

  await page.addInitScript(() => {
    localStorage.setItem('agent_editor_profile', JSON.stringify({
      userId: 'smoke-user', knowledgeDir: 'D:/Knowledge', knowledgeLibraries: [], knowledgeWatchEnabled: true,
    }))
  })
  await page.route('**/*', async (route) => {
    const request = route.request()
    if (request.resourceType() !== 'fetch' && request.resourceType() !== 'xhr') {
      await route.continue()
      return
    }
    const url = new URL(request.url())
    if (url.pathname === '/settings/models/status') {
      await route.fulfill({ json: { embedding: 'ready', rerank: 'ready' } })
      return
    }
    if (url.pathname === '/settings/profile') {
      await route.fulfill({ json: { user_id: 'smoke-user', knowledge_dir: 'D:/Knowledge', knowledge_libraries: [] } })
      return
    }
    if (url.pathname === '/knowledge/files') {
      await route.fulfill({ json: { tree: jobs().map((job) => ({
        name: job.name, path: job.path, isDir: false, size: job.size, mtime: job.mtime, indexStatus: 'dirty',
      })) } })
      return
    }
    if (url.pathname === '/knowledge/ingestion/jobs' && request.method() === 'POST') {
      await route.fulfill({ json: { jobs: jobs() } })
      return
    }
    if (url.pathname === '/knowledge/ingestion/jobs' && request.method() === 'GET') {
      await route.fulfill({ json: { jobs: jobs() } })
      return
    }
    if (url.pathname === '/knowledge/ingestion/jobs/ingest_pdf/cancel') {
      pdfCancelled = true
      await route.fulfill({ json: jobs()[0] })
      return
    }
    await route.fulfill({ json: {} })
  })

  await page.goto('/')
  await page.getByTitle('重新灌库').click()

  await expect(page.locator('.queue-table .progress-detail').filter({ hasText: '正在 OCR 扫描页' })).toBeVisible()
  await expect(page.getByText('8 / 20')).toBeVisible()
  await expect(page.locator('.queue-table .progress-detail').filter({ hasText: '正在解析工作表' })).toBeVisible()
  await expect(page.getByText('2 / 5')).toBeVisible()
  await expect(page.locator('.queue-table .progress-detail').filter({ hasText: 'Markdown 标题解析完成，共 6 个章节' })).toBeVisible()
  await expect(page.getByText('D:\\Knowledge\\paper.pdf', { exact: true })).toBeVisible()
  await expect(page.getByText('D:\\Knowledge\\table.xlsx', { exact: true })).toBeVisible()
  await expect(page.getByText('D:\\Knowledge\\notes.md', { exact: true })).toBeVisible()
  const headerProgress = page.locator('.topbar .ingestion-progress:not(.graph-progress)')
  await expect(headerProgress.locator('.ingestion-progress-label')).toContainText('入库 0/3 · paper.pdf · 正在 OCR 扫描页 · 8/20')
  await page.screenshot({ path: testInfo.outputPath('ingestion-header-detail-desktop.png'), fullPage: true })

  await page.getByRole('button', { name: '中止 paper.pdf 灌库' }).click()
  await expect(page.locator('.file-table-body .file-name[title="paper.pdf"]')).toHaveCount(0)
  await expect(headerProgress.locator('.ingestion-progress-label')).toContainText('入库 1/3 · table.xlsx · 正在解析工作表 · 2/5')
  await expect(headerProgress.locator('.ingestion-progress-percent')).toHaveText('58%')
  await page.getByRole('tab', { name: '入库历史' }).click()
  await expect(page.getByText('已中止', { exact: true })).toBeVisible()
  await expect(page.getByText('用户中止灌库')).toBeVisible()
})

test('cancels a graph row and refreshes queue plus header status across responsive widths', async ({ page }, testInfo) => {
  let cancelled = false
  const graphDocs = () => [{
    path: 'notes/graph.md', name: 'graph.md', status: cancelled ? 'cancelled' : 'processing',
    progress: cancelled ? 100 : 46, stage: cancelled ? 'cancelled' : 'extracting',
    stage_label: cancelled ? '已中止图谱抽取' : '正在抽取实体',
    stage_current: cancelled ? 0 : 2, stage_total: cancelled ? 0 : 4,
    message: cancelled ? '图谱抽取已中止' : '正在处理章节 2/4',
  }]

  await page.addInitScript(() => {
    localStorage.setItem('agent_editor_profile', JSON.stringify({
      userId: 'graph-smoke-user', knowledgeDir: 'D:/Knowledge', activeLibraryId: 'kb1',
      knowledgeLibraries: [{ libraryId: 'kb1', name: 'KB', knowledgeDir: 'D:/Knowledge', isActive: true }],
    }))
  })
  await page.route('**/*', async (route) => {
    const request = route.request()
    if (request.resourceType() !== 'fetch' && request.resourceType() !== 'xhr') {
      await route.continue()
      return
    }
    const url = new URL(request.url())
    if (url.pathname === '/settings/models/status') return route.fulfill({ json: { embedding: 'ready', rerank: 'ready' } })
    if (url.pathname === '/settings/profile') return route.fulfill({ json: {
      user_id: 'graph-smoke-user', knowledge_dir: 'D:/Knowledge', active_library_id: 'kb1',
      knowledge_libraries: [{ library_id: 'kb1', name: 'KB', knowledge_dir: 'D:/Knowledge', is_active: true }],
    } })
    if (url.pathname === '/knowledge/files') return route.fulfill({ json: { tree: [{
      name: 'graph.md', path: 'notes/graph.md', isDir: false, indexStatus: 'indexed', graphStatus: 'dirty',
    }] } })
    if (url.pathname === '/knowledge/graph/rebuild' && request.method() === 'POST') {
      return route.fulfill({ json: { status: 'queued', message: '图谱任务已加入队列' } })
    }
    if (url.pathname === '/knowledge/graph/rebuild/cancel') {
      cancelled = true
      return route.fulfill({ json: { status: 'cancelling', message: '图谱任务正在中止' } })
    }
    if (url.pathname === '/knowledge/graph/rebuild/status') return route.fulfill({ json: {
      status: cancelled ? 'cancelled' : 'running', total: 1, current: cancelled ? 1 : 0,
      message: cancelled ? '图谱抽取已中止' : '正在处理章节 2/4', docs: graphDocs(),
    } })
    if (url.pathname === '/knowledge/ingestion/jobs') return route.fulfill({ json: { jobs: [] } })
    if (url.pathname === '/knowledge/files/trash') return route.fulfill({ json: { entries: [] } })
    return route.fulfill({ json: {} })
  })

  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/')
  await page.getByTitle('图谱抽取').click()
  const graphHeader = page.locator('.topbar .graph-progress')
  await expect(graphHeader.locator('.graph-progress-label')).toContainText('图谱 0/1 · 正在抽取实体 2/4')
  await expect(page.getByRole('button', { name: '中止 graph.md 图谱抽取' })).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('graph-cancel-desktop.png'), fullPage: true })

  await page.setViewportSize({ width: 768, height: 900 })
  await expect(page.getByRole('button', { name: '中止 graph.md 图谱抽取' })).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('graph-cancel-tablet.png'), fullPage: true })
  await page.setViewportSize({ width: 480, height: 860 })
  await expect(page.getByRole('button', { name: '中止 graph.md 图谱抽取' })).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('graph-cancel-mobile.png'), fullPage: true })

  await page.getByRole('button', { name: '中止 graph.md 图谱抽取' }).click()
  await expect(page.locator('.graph-queue-table .file-row')).toHaveCount(0)
  await expect(graphHeader.locator('.graph-progress-label')).toContainText('图谱 1/1 · 图谱抽取已中止')
  await expect(graphHeader.locator('.ingestion-progress-percent')).toHaveText('100%')
})
