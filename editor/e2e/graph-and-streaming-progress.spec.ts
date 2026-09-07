/**
 * Browser smoke checks for detailed graph progress and live Agent Markdown.
 *
 * Usage:
 * Exercises the real workspace UI with deterministic API responses and a
 * browser ReadableStream so intermediate Markdown states are observable.
 */
import { expect, test } from '@playwright/test'

const profile = {
  userId: 'smoke-user',
  knowledgeDir: 'D:/Knowledge',
  activeLibraryId: 'kb1',
  knowledgeLibraries: [{
    libraryId: 'kb1', name: 'knowledge', knowledgeDir: 'D:/Knowledge',
    libraryStorageDir: '.mw/library', isActive: true,
  }],
}

test('shows responsive graph pipeline and section progress', async ({ page }) => {
  let graphPolls = 0
  const finishedJob = {
    job_id: 'ingest-1', user_id: 'smoke-user', library_id: 'kb1', path: 'notes.md', name: 'notes.md',
    pipeline: 'markdown', status: 'finished', stage: 'finished', stage_label: '灌库完成', progress: 100,
    stage_current: 1, stage_total: 1, size: 1024, mtime: '2026-08-20T10:00:00Z', message: '', error: '',
    created_at: '2026-08-20T10:00:00Z', started_at: '2026-08-20T10:00:00Z', finished_at: '2026-08-20T10:00:01Z',
    updated_at: '2026-08-20T10:00:01Z',
  }
  await page.addInitScript((storedProfile) => {
    localStorage.setItem('agent_editor_profile', JSON.stringify(storedProfile))
  }, profile)
  await page.route('**/*', async (route) => {
    const request = route.request()
    if (!['fetch', 'xhr'].includes(request.resourceType())) return route.continue()
    const path = new URL(request.url()).pathname
    if (path === '/settings/models/status') return route.fulfill({ json: { embedding: 'ready', rerank: 'ready' } })
    if (path === '/settings/profile') return route.fulfill({ json: {
      user_id: 'smoke-user', knowledge_dir: 'D:/Knowledge', active_library_id: 'kb1',
      knowledge_libraries: [{ library_id: 'kb1', name: 'knowledge', knowledge_dir: 'D:/Knowledge', library_storage_dir: '.mw/library', is_active: true }],
    } })
    if (path === '/knowledge/files') return route.fulfill({ json: { tree: [{
      name: 'notes.md', path: 'notes.md', isDir: false, size: 1024,
      mtime: '2026-08-20 18:00', indexStatus: 'dirty', graphStatus: 'dirty',
    }] } })
    if (path === '/knowledge/ingestion/jobs') return route.fulfill({ json: { jobs: [finishedJob] } })
    if (path === '/knowledge/graph/rebuild') return route.fulfill({ json: { status: 'started', message: 'started' } })
    if (path === '/knowledge/graph/rebuild/status') {
      graphPolls += 1
      return route.fulfill({ json: {
        status: 'running', total: 2, current: 0, message: '文档 1/2 已抽取 2/5 个章节，完成 1/2 批请求',
        docs: [
          { path: 'notes.md', name: 'notes', status: 'processing', progress: 45, stage: 'extract_sections', stage_label: '本地并发候选抽取', stage_current: 2, stage_total: 5, message: '已完成 1/2 批请求' },
          { path: 'next.md', name: 'next', status: 'pending', progress: 0, stage: 'waiting', stage_label: '等待图谱抽取', stage_current: 0, stage_total: 3 },
        ],
      } })
    }
    if (path === '/sessions') return route.fulfill({ json: [] })
    if (path === '/agent/children') return route.fulfill({ json: { children: [] } })
    return route.fulfill({ json: {} })
  })

  await page.goto('/')
  await page.locator('.topbar button[title="图谱抽取"]').click()
  await expect(page.locator('.graph-progress-cell .progress-detail').first()).toContainText('本地并发候选抽取')
  await expect(page.getByText('2 / 5', { exact: false })).toBeVisible()
  await expect(page.getByText('D:\\Knowledge\\notes.md', { exact: true })).toBeVisible()
  await expect(page.getByText('D:\\Knowledge\\next.md', { exact: true })).toBeVisible()
  await expect(page.locator('.graph-progress .ingestion-progress-percent')).toHaveText('23%')
  await expect(page.locator('.graph-progress-label')).toContainText('图谱 0/2 · 本地并发候选抽取 2/5')
  await expect.poll(() => graphPolls, { timeout: 1400 }).toBeGreaterThanOrEqual(2)
})

test('renders streamed lists, tables, and code before the stream closes', async ({ page }) => {
  let historyRequests = 0
  await page.addInitScript((storedProfile) => {
    localStorage.setItem('agent_editor_profile', JSON.stringify(storedProfile))
    const nativeFetch = window.fetch.bind(window)
    window.fetch = async (input, init) => {
      const url = new URL(typeof input === 'string' ? input : input instanceof URL ? input.href : input.url, location.href)
      if (url.pathname !== '/agent/stream') return nativeFetch(input, init)
      ;(window as typeof window & { __streamCalls?: number }).__streamCalls = ((window as typeof window & { __streamCalls?: number }).__streamCalls ?? 0) + 1
      const encoder = new TextEncoder()
      const chunks = [
        '- 第一项',
        '\n- 第二项',
        '\n\n| 名称 | 状态 |\n| --- | --- |\n| 图谱 | 抽取中 |',
        '\n\n```ts\nconst live = true',
      ]
      const stream = new ReadableStream({
        start(controller) {
          chunks.forEach((content, index) => window.setTimeout(() => {
            controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: 'delta', node: 'agent', content })}\n\n`))
          }, index * 180))
          window.setTimeout(() => controller.close(), 1400)
        },
      })
      return new Response(stream, { status: 200, headers: { 'Content-Type': 'text/event-stream' } })
    }
  }, profile)
  await page.route('**/*', async (route) => {
    const request = route.request()
    if (!['fetch', 'xhr'].includes(request.resourceType())) return route.continue()
    const path = new URL(request.url()).pathname
    if (path === '/settings/models/status') return route.fulfill({ json: { embedding: 'ready', rerank: 'ready' } })
    if (path === '/settings/profile') return route.fulfill({ json: { user_id: 'smoke-user', knowledge_dir: 'D:/Knowledge', knowledge_libraries: [] } })
    if (path === '/sessions' && request.method() === 'POST') return route.fulfill({ json: {
      session_id: 'stream-session', user_id: 'smoke-user', session_name: 'stream',
      created_at: '2026-08-20T10:00:00Z', updated_at: '2026-08-20T10:00:00Z',
    } })
    if (path === '/sessions') return route.fulfill({ json: [] })
    if (path.endsWith('/messages')) {
      historyRequests += 1
      return route.fulfill({ json: [] })
    }
    if (path === '/agent/task-suggestions') return route.fulfill({ json: { suggestions: [] } })
    if (path === '/agent/children') return route.fulfill({ json: { children: [] } })
    if (path === '/knowledge/files') return route.fulfill({ json: { tree: [] } })
    return route.fulfill({ json: {} })
  })

  await page.goto('/')
  const input = page.getByPlaceholder('输入消息...')
  await expect(input).toBeVisible()
  await input.fill('测试流式 Markdown')
  await input.press('Enter')

  await expect.poll(() => page.evaluate(() => (window as typeof window & { __streamCalls?: number }).__streamCalls ?? 0)).toBe(1)
  await page.waitForTimeout(100)
  expect(historyRequests).toBe(0)
  const markdown = page.locator('.markdown-body')
  await expect(markdown.locator('li')).toHaveCount(2)
  await expect(markdown.locator('tbody tr')).toHaveCount(1)
  await expect(markdown.locator('pre code')).toContainText('const live = true')
  await expect(page.getByTitle('中断输出')).toBeVisible()
  await expect(markdown.locator('.stream-reveal-word, .stream-cursor')).toHaveCount(0)
})

test('floating Agent renders incremental text before completion and keeps the shared titlebar responsive', async ({ page }) => {
  await page.addInitScript((storedProfile) => {
    localStorage.setItem('agent_editor_profile', JSON.stringify(storedProfile))
    const nativeFetch = window.fetch.bind(window)
    window.fetch = async (input, init) => {
      const url = new URL(typeof input === 'string' ? input : input instanceof URL ? input.href : input.url, location.href)
      if (url.pathname !== '/agent/stream') return nativeFetch(input, init)
      const encoder = new TextEncoder()
      const stream = new ReadableStream({
        start(controller) {
          window.setTimeout(() => controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: 'delta', node: 'agent', content: '第一段' })}\n\n`)), 80)
          window.setTimeout(() => controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: 'delta', node: 'agent', content: '第二段' })}\n\n`)), 480)
          window.setTimeout(() => controller.close(), 1600)
        },
      })
      return new Response(stream, { status: 200, headers: { 'Content-Type': 'text/event-stream' } })
    }
  }, profile)
  await page.route('**/*', async (route) => {
    const request = route.request()
    if (!['fetch', 'xhr'].includes(request.resourceType())) return route.continue()
    const path = new URL(request.url()).pathname
    if (path === '/health') return route.fulfill({ json: { status: 'ok' } })
    if (path === '/settings/models/status') return route.fulfill({ json: { embedding: 'ready', rerank: 'ready' } })
    if (path === '/settings/profile') return route.fulfill({ json: { user_id: 'smoke-user', knowledge_dir: 'D:/Knowledge', knowledge_libraries: [] } })
    if (path === '/settings/llm') return route.fulfill({ json: { model_name: 'smoke-model', context_window_tokens: 128000 } })
    if (path === '/sessions' && request.method() === 'POST') return route.fulfill({ json: {
      session_id: 'floating-stream-session', user_id: 'smoke-user', session_name: 'floating stream',
      created_at: '2026-08-22T00:00:00Z', updated_at: '2026-08-22T00:00:00Z',
    } })
    if (path === '/sessions') return route.fulfill({ json: [] })
    if (path.endsWith('/messages')) return route.fulfill({ json: [] })
    if (path === '/agent/task-suggestions') return route.fulfill({ json: { suggestions: [] } })
    if (path === '/agent/children') return route.fulfill({ json: { children: [] } })
    if (path === '/knowledge/files') return route.fulfill({ json: { tree: [] } })
    return route.fulfill({ json: {} })
  })

  await page.setViewportSize({ width: 460, height: 632 })
  await page.goto('/?floating=1')
  const input = page.locator('.collapsed-input').getByPlaceholder('输入消息...')
  await expect(input).toBeVisible()
  await input.fill('验证悬浮窗流式输出')
  await input.press('Enter')

  const markdown = page.locator('.markdown-body')
  await expect(markdown).toContainText('第一段')
  await expect(page.getByTitle('中断输出')).toBeVisible()
  await expect(page.locator('.floating-agent-panel.agent-panel')).toBeVisible()
  await expect(page.locator('.agent-panel-titlebar.compact')).toBeVisible()
  await expect(page.locator('.agent-panel-titlebar button[title="任务列表"]')).toBeHidden()
  await expect(page.getByTitle('新对话')).toBeVisible()
  await expect(markdown).toContainText('第一段第二段')
  await expect(page.getByTitle('中断输出')).toBeVisible()
  await expect(page.getByTitle('折叠为输入框')).toBeVisible()
})

test('floating and sidebar Agent views share the selected conversation and live stream', async ({ browser }) => {
  const context = await browser.newContext()
  const relayedTypes: string[] = []
  await context.exposeBinding('__relayAgentWindowSync', async (source, type: string, value: unknown) => {
    relayedTypes.push(type)
    await Promise.allSettled(context.pages()
      .filter((target) => target !== source.page)
      .map((target) => target.evaluate(({ eventType, eventValue }) => {
        const callbacks = (window as typeof window & { __agentSyncCallbacks?: Array<(payload: unknown) => void> }).__agentSyncCallbacks ?? []
        callbacks.forEach((callback) => callback({ type: eventType, value: eventValue }))
      }, { eventType: type, eventValue: value })))
  })
  await context.addInitScript((storedProfile) => {
    localStorage.setItem('agent_editor_profile', JSON.stringify(storedProfile))
    const syncWindow = window as typeof window & {
      __agentSyncCallbacks?: Array<(payload: { type: string; value: unknown }) => void>
      __relayAgentWindowSync?: (type: string, value: unknown) => Promise<void>
    }
    syncWindow.__agentSyncCallbacks = []
    Object.defineProperty(window, 'agentEditorDesktop', {
      configurable: true,
      value: {
        windowSync: (type: string, value: unknown) => void syncWindow.__relayAgentWindowSync?.(type, value),
        onWindowSync: (callback: (payload: { type: string; value: unknown }) => void) => {
          syncWindow.__agentSyncCallbacks?.push(callback)
          return () => {
            syncWindow.__agentSyncCallbacks = syncWindow.__agentSyncCallbacks?.filter((item) => item !== callback)
          }
        },
        floatingSetBounds: async () => undefined,
        floatingSetAlwaysOnTop: async () => 'normal',
        floatingSetVisible: async () => true,
        floatingClose: () => undefined,
        openAgentPage: () => undefined,
      },
    })
    const nativeFetch = window.fetch.bind(window)
    window.fetch = async (input, init) => {
      const url = new URL(typeof input === 'string' ? input : input instanceof URL ? input.href : input.url, location.href)
      if (url.pathname !== '/agent/stream') return nativeFetch(input, init)
      const encoder = new TextEncoder()
      const stream = new ReadableStream({
        start(controller) {
          window.setTimeout(() => controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: 'delta', node: 'agent', content: '窗口同步第一段' })}\n\n`)), 250)
          window.setTimeout(() => controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: 'delta', node: 'agent', content: '，第二段' })}\n\n`)), 2500)
          window.setTimeout(() => controller.close(), 8000)
        },
      })
      return new Response(stream, { status: 200, headers: { 'Content-Type': 'text/event-stream' } })
    }
  }, profile)

  const installRoutes = async (target: import('@playwright/test').Page) => {
    await target.route('**/*', async (route) => {
      const request = route.request()
      if (!['fetch', 'xhr'].includes(request.resourceType())) return route.continue()
      const path = new URL(request.url()).pathname
      if (path === '/health') return route.fulfill({ json: { status: 'ok' } })
      if (path === '/settings/models/status') return route.fulfill({ json: { embedding: 'ready', rerank: 'ready' } })
      if (path === '/settings/profile') return route.fulfill({ json: { user_id: 'smoke-user', knowledge_dir: 'D:/Knowledge', knowledge_libraries: [] } })
      if (path === '/settings/llm') return route.fulfill({ json: { model_name: 'smoke-model', context_window_tokens: 128000 } })
      if (path === '/sessions' && request.method() === 'POST') return route.fulfill({ json: {
        session_id: 'cross-window-session', user_id: 'smoke-user', session_name: 'cross window',
        created_at: '2026-08-22T00:00:00Z', updated_at: '2026-08-22T00:00:00Z',
      } })
      if (path === '/sessions') return route.fulfill({ json: [] })
      if (path.endsWith('/messages')) return route.fulfill({ json: [] })
      if (path === '/agent/task-suggestions') return route.fulfill({ json: { suggestions: [] } })
      if (path === '/agent/children') return route.fulfill({ json: { children: [] } })
      if (path === '/knowledge/files') return route.fulfill({ json: { tree: [] } })
      return route.fulfill({ json: {} })
    })
  }

  const sidebar = await context.newPage()
  const floating = await context.newPage()
  await floating.setViewportSize({ width: 460, height: 632 })
  await installRoutes(sidebar)
  await installRoutes(floating)
  await Promise.all([sidebar.goto('/'), floating.goto('/?floating=1')])
  await sidebar.getByRole('button', { name: 'Agent', exact: true }).click()
  await expect(sidebar.getByPlaceholder('输入消息...')).toBeVisible()
  const floatingInput = floating.locator('.collapsed-input').getByPlaceholder('输入消息...')
  await expect(floatingInput).toBeVisible()
  await floatingInput.fill('从悬浮窗提出的新问题')
  await floatingInput.press('Enter')

  await expect.poll(() => relayedTypes).toContain('session')
  await expect.poll(() => relayedTypes).toContain('chat-state')
  await expect.poll(() => sidebar.evaluate(() => localStorage.getItem('agent_editor_active_session_id')))
    .toBe('cross-window-session')
  await expect(sidebar.getByText('从悬浮窗提出的新问题', { exact: true })).toBeVisible()
  await expect(sidebar.locator('.markdown-body')).toContainText('窗口同步第一段')
  await expect(sidebar.getByTitle('中断输出')).toBeVisible()
  await expect(sidebar.locator('.markdown-body')).toContainText('窗口同步第一段，第二段')
  await sidebar.getByTitle('中断输出').click()
  await expect(floating.getByTitle('中断输出')).toHaveCount(0)
  await context.close()
})
