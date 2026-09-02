/*
 * 子 Agent 终态提示浏览器回归。
 *
 * 用途：通过真实 Agent 页面消费两个子 Agent 的 created/completed SSE，验证完成条
 * 数量与创建数量一致，并确认每个终态只调用一次服务端 wakeup claim。
 */
import { expect, test } from '@playwright/test'

test('renders one completion row and one wakeup claim per child agent', async ({ page }, testInfo) => {
  let sessionCreated = false
  const claimedRunIds: string[] = []
  const projectedHistory = [
    {
      message_id: 'history-user',
      session_id: 'e2e-session',
      role: 'user',
      content: '继续等待',
      metadata: {},
      created_at: '2026-09-01T00:00:00Z',
    },
    {
      message_id: 'history-wait',
      session_id: 'e2e-session',
      role: 'tool',
      content: '{"result": null, "children": []}',
      tool_call_id: 'wait-history',
      metadata: {
        node: 'action',
        trace: [{
          node: 'action',
          event: 'tool_call_end',
          tool_call_id: 'wait-history',
          tool_name: 'wait_for_child_agents',
          display_name: '等待子 Agent',
          raw_content: '{"result": null, "children": []}',
          chat_visible: true,
        }],
      },
      created_at: '2026-09-01T00:00:01Z',
    },
    {
      message_id: 'history-agent',
      session_id: 'e2e-session',
      role: 'assistant',
      content: '历史最终回复：继续等待最后一个子 Agent。',
      metadata: { node: 'agent' },
      created_at: '2026-09-01T00:00:02Z',
    },
  ]

  await page.route('**/*', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    if (url.pathname === '/agent/stream') {
      const events = ['explore1', 'explore2'].flatMap((name, index) => {
        const child = {
          run_id: `child-e2e-${index + 1}`,
          goal: `并行任务 ${index + 1}`,
          name,
          mode: 'background',
          access_mode: 'readonly',
          allowed_tools: [],
        }
        return [
          {
            type: 'child_agent_event',
            node: 'child_agent',
            metadata: {
              child_agent_event: {
                event_name: 'child_agent.created',
                child: { ...child, status: 'created' },
              },
            },
          },
          {
            type: 'child_agent_event',
            node: 'child_agent',
            metadata: {
              child_agent_event: {
                event_name: 'child_agent.completed',
                child: { ...child, status: 'completed', summary: '完成' },
              },
            },
          },
        ]
      })
      const body = `${events.map((event) => `data: ${JSON.stringify(event)}\n\n`).join('')}data: [DONE]\n\n`
      await route.fulfill({ status: 200, contentType: 'text/event-stream', body })
      return
    }
    if (/^\/agent\/children\/[^/]+\/claim-wakeup$/.test(url.pathname)) {
      const runId = decodeURIComponent(url.pathname.split('/')[3] ?? '')
      claimedRunIds.push(runId)
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ run_id: runId, claimed: true }),
      })
      return
    }
    if (url.pathname === '/settings/profile') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          user_id: 'e2e-user',
          knowledge_dir: 'D:/Knowledge',
          active_library_id: 'default',
          knowledge_libraries: [],
        }),
      })
      return
    }
    if (url.pathname === '/sessions' && request.method() === 'POST') {
      sessionCreated = true
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          session_id: 'e2e-session',
          user_id: 'e2e-user',
          session_name: 'child-agent-dedup',
          created_at: '',
          updated_at: '',
        }),
      })
      return
    }
    if (url.pathname === '/sessions' && request.method() === 'GET') {
      const sessions = sessionCreated
        ? [{
            session_id: 'e2e-session',
            user_id: 'e2e-user',
            session_name: 'child-agent-dedup',
            created_at: '',
            updated_at: '',
          }]
        : []
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(sessions) })
      return
    }
    if (url.pathname === '/agent/children') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ session_id: 'e2e-session', children: [] }),
      })
      return
    }
    if (url.pathname.endsWith('/messages')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(sessionCreated ? projectedHistory : []),
      })
      return
    }
    if (url.pathname === '/favorites') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ favorites: [] }) })
      return
    }
    if (url.pathname === '/privacy') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ privacy: [] }) })
      return
    }
    if (url.pathname === '/skills') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ skills: [], count: 0 }) })
      return
    }
    if (url.pathname === '/knowledge/files') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ tree: [] }) })
      return
    }
    if (url.pathname === '/knowledge/files/events') {
      await route.fulfill({ status: 200, contentType: 'text/event-stream', body: '' })
      return
    }
    if (url.pathname === '/settings/models/status' || url.pathname === '/settings/models/management') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ models: [] }) })
      return
    }
    if (url.pathname === '/settings/llm/config') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ model_name: '' }) })
      return
    }
    if (url.pathname === '/settings/web-search/config') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ enabled: false }) })
      return
    }
    if (url.pathname === '/todo/list' || url.pathname === '/automation/list') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
      return
    }
    if (url.pathname === '/git/status') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          initialized: false,
          branches: [],
          remote_branches: [],
          remotes: [],
          changes: [],
          untracked: [],
          ignored: [],
          has_changes: false,
        }),
      })
      return
    }
    if (url.pathname === '/git/history') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ history: [], unpushed_commits: [], unpushed_files: [], upstream: '' }),
      })
      return
    }
    if (url.pathname.endsWith('/changes')) {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ change_snapshot: null }) })
      return
    }
    if (url.pathname.endsWith('/task-list')) {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ task_list: null }) })
      return
    }
    if (url.pathname.endsWith('/state')) {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ session_state: null }) })
      return
    }
    if (url.pathname.includes('task-suggestions')) {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ suggestions: [] }) })
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
      userId: 'e2e-user',
      knowledgeDir: 'D:/Knowledge',
      activeLibraryId: 'default',
      knowledgeLibraries: [],
    }))
    localStorage.setItem('agent_editor_chat_mode', 'chat')
  })
  await page.goto('/')
  await page.getByRole('button', { name: 'Agent', exact: true }).click()
  await page.locator('textarea[placeholder="输入消息..."]').fill('并行调查')
  await page.getByRole('button', { name: '发送' }).click()

  await expect(page.getByText(/^子 Agent 已创建：/)).toHaveCount(2)
  await expect(page.getByText(/^子 Agent 完成任务：/)).toHaveCount(2)
  await expect(page.locator('.child-agent-event[data-status="completed"]')).toHaveCount(2)
  expect(claimedRunIds.sort()).toEqual(['child-e2e-1', 'child-e2e-2'])
  await page.screenshot({ path: testInfo.outputPath('child-agent-completion-dedup.png'), fullPage: true })

  await page.reload()
  await page.getByRole('button', { name: 'Agent', exact: true }).click()
  await page.locator('.session-item').filter({ hasText: 'child-agent-dedup' }).evaluate((element) => {
    ;(element as HTMLElement).click()
  })
  await expect(page.getByText('历史最终回复：继续等待最后一个子 Agent。')).toHaveCount(1)
  await expect(page.locator('.tool-call-box')).toHaveCount(1)
  await page.screenshot({ path: testInfo.outputPath('agent-history-reloaded.png'), fullPage: true })
})
