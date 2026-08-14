import { expect, test } from '@playwright/test'

test('automation sidebar pause, resume, and deletion stay synchronized with the scheduler', async ({ page }) => {
  let deleted = false
  let enabled = true
  let automationDeleteCalls = 0
  let ordinaryTodoDeleteCalls = 0
  const todo = {
    id: 'todo-automation-e2e',
    text: '日报',
    category: 'automation',
    done: false,
    createdAt: '2026-08-14T00:00:00.000Z',
    recurrence: { frequency: 'none', interval: 1 },
  }
  const automation = () => ({
    id: 'automation-e2e',
    todoId: todo.id,
    userId: 'e2e-user',
    prompt: '整理当天工作并生成日报',
    timezone: 'Asia/Shanghai',
    recurrence: { frequency: 'daily', interval: 1 },
    nextRunAt: '2099-08-15T01:00:00.000Z',
    accessMode: 'sandbox',
    enabled,
    lastRunAt: null,
    lastStatus: null,
    lastError: null,
  })

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
          user_id: 'e2e-user',
          knowledge_dir: 'D:/Knowledge',
          active_library_id: 'default',
          knowledge_libraries: [],
        }),
      })
      return
    }
    if (request.method() === 'GET' && url.pathname === '/todo/list') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(deleted ? [] : [todo]),
      })
      return
    }
    if (request.method() === 'GET' && url.pathname === '/automation/list') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(deleted ? [] : [automation()]),
      })
      return
    }
    if (request.method() === 'POST' && url.pathname === '/automation/toggle') {
      const body = request.postDataJSON() as { enabled: boolean }
      enabled = body.enabled
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(automation()),
      })
      return
    }
    if (request.method() === 'POST' && url.pathname === '/automation/delete') {
      automationDeleteCalls += 1
      deleted = true
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ deleted: true }),
      })
      return
    }
    if (request.method() === 'POST' && url.pathname === '/todo/delete') {
      ordinaryTodoDeleteCalls += 1
      await route.fulfill({ status: 200, contentType: 'application/json', body: '{"deleted":true}' })
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
  })
  await page.setViewportSize({ width: 1280, height: 800 })
  await page.goto('/')
  await page.getByTitle('待办').click()

  const row = page.locator('[data-todo-id="todo-automation-e2e"]')
  await expect(row).toBeVisible()
  await expect(row.locator('input[type="checkbox"]')).toHaveCount(0)
  await row.getByRole('button', { name: '暂停自动化：日报' }).click()
  await expect(row.getByRole('button', { name: '恢复自动化：日报' })).toBeVisible()
  await row.getByRole('button', { name: '恢复自动化：日报' }).click()
  await expect(row.getByRole('button', { name: '暂停自动化：日报' })).toBeVisible()

  await row.getByRole('button', { name: '删除自动化：日报' }).click()
  expect(automationDeleteCalls).toBe(0)
  await expect(row).toContainText('将取消未来执行并删除运行记录')
  await row.getByRole('button', { name: '确认删除自动化：日报' }).click()

  await expect(row).toHaveCount(0)
  expect(automationDeleteCalls).toBe(1)
  expect(ordinaryTodoDeleteCalls).toBe(0)

  await page.reload()
  await page.getByTitle('待办').click()
  await expect(page.locator('[data-todo-id="todo-automation-e2e"]')).toHaveCount(0)
})
