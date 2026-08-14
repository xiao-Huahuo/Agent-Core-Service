/**
 * TODO store automation lifecycle tests.
 *
 * Verifies that automation rows use the owning automation endpoints for
 * deletion and enablement while ordinary TODO behavior remains unchanged.
 */

import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { TodoItemData } from '@/api/todo'
import { useTodoStore } from '@/stores/todo'

const api = vi.hoisted(() => ({
  apiDeleteAutomation: vi.fn(),
  apiToggleAutomation: vi.fn(),
  apiDeleteTodo: vi.fn(),
  apiToggleTodo: vi.fn(),
  apiListAutomations: vi.fn(),
  apiListTodos: vi.fn(),
}))

vi.mock('@/api/automation', () => ({
  apiAddAutomation: vi.fn(),
  apiDeleteAutomation: api.apiDeleteAutomation,
  apiListAutomations: api.apiListAutomations,
  apiToggleAutomation: api.apiToggleAutomation,
}))

vi.mock('@/api/todo', () => ({
  apiAddTodo: vi.fn(),
  apiDeleteTodo: api.apiDeleteTodo,
  apiEditTodo: vi.fn(),
  apiListTodos: api.apiListTodos,
  apiToggleTodo: api.apiToggleTodo,
}))

vi.mock('@/stores/settings', () => ({
  useSettingsStore: () => ({ profile: { userId: 'u1' } }),
}))

const automation = {
  id: 'automation_1',
  todoId: 'todo_automation',
  prompt: '整理日报',
  timezone: 'Asia/Shanghai',
  recurrence: { frequency: 'daily' as const, interval: 1 },
  nextRunAt: '2026-08-15T01:00:00+00:00',
  accessMode: 'sandbox' as const,
  enabled: true,
}

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

describe('todo store automation lifecycle', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    api.apiDeleteAutomation.mockResolvedValue({ deleted: true })
    api.apiDeleteTodo.mockResolvedValue({ deleted: true })
    api.apiToggleAutomation.mockImplementation(async (_userId, _automationId, enabled) => ({
      ...automation,
      enabled,
    }))
    api.apiListAutomations.mockResolvedValue([])
    api.apiListTodos.mockResolvedValue([])
  })

  it('deletes an automation through its canonical endpoint and removes both local records', async () => {
    const store = useTodoStore()
    store.todos.push({
      id: automation.todoId,
      text: '日报',
      category: 'automation',
      done: false,
      createdAt: '2026-08-14T00:00:00Z',
      recurrence: { frequency: 'none', interval: 1 },
    })
    store.automations.push(automation)

    expect(await store.removeTodo(automation.todoId)).toBe(true)

    expect(api.apiDeleteAutomation).toHaveBeenCalledWith('u1', automation.id)
    expect(api.apiDeleteTodo).not.toHaveBeenCalled()
    expect(store.todos).toHaveLength(0)
    expect(store.automations).toHaveLength(0)
  })

  it('keeps the automation visible and exposes an actionable error when deletion fails', async () => {
    api.apiDeleteAutomation.mockRejectedValueOnce(new Error('数据库忙'))
    const store = useTodoStore()
    store.todos.push({
      id: automation.todoId,
      text: '日报',
      category: 'automation',
      done: false,
      createdAt: '2026-08-14T00:00:00Z',
      recurrence: { frequency: 'none', interval: 1 },
    })
    store.automations.push(automation)

    expect(await store.removeTodo(automation.todoId)).toBe(false)

    expect(store.todos).toHaveLength(1)
    expect(store.automations).toHaveLength(1)
    expect(store.automationActionErrors[automation.todoId]).toContain('数据库忙')
  })

  it('routes an automation checkbox toggle to the scheduler enablement endpoint', async () => {
    const store = useTodoStore()
    store.todos.push({
      id: automation.todoId,
      text: '日报',
      category: 'automation',
      done: false,
      createdAt: '2026-08-14T00:00:00Z',
      recurrence: { frequency: 'none', interval: 1 },
    })
    store.automations.push(automation)

    await store.toggleTodo(automation.todoId)

    expect(api.apiToggleAutomation).toHaveBeenCalledWith('u1', automation.id, false)
    expect(api.apiToggleTodo).not.toHaveBeenCalled()
    expect(store.automations[0]?.enabled).toBe(false)
  })

  it('fails closed when an automation TODO is missing its scheduler metadata', async () => {
    const store = useTodoStore()
    store.todos.push({
      id: automation.todoId,
      text: '日报',
      category: 'automation',
      done: false,
      createdAt: '2026-08-14T00:00:00Z',
      recurrence: { frequency: 'none', interval: 1 },
    })

    expect(await store.removeTodo(automation.todoId)).toBe(false)

    expect(api.apiDeleteAutomation).not.toHaveBeenCalled()
    expect(api.apiDeleteTodo).not.toHaveBeenCalled()
    expect(store.todos).toHaveLength(1)
    expect(store.automationActionErrors[automation.todoId]).toContain('元数据')
  })

  it('rolls back a failed pause request', async () => {
    api.apiToggleAutomation.mockRejectedValueOnce(new Error('网络失败'))
    const store = useTodoStore()
    store.todos.push({
      id: automation.todoId,
      text: '日报',
      category: 'automation',
      done: false,
      createdAt: '2026-08-14T00:00:00Z',
      recurrence: { frequency: 'none', interval: 1 },
    })
    store.automations.push(automation)

    expect(await store.setAutomationEnabled(automation.todoId, false)).toBe(false)

    expect(store.automations[0]?.enabled).toBe(true)
    expect(store.automationActionErrors[automation.todoId]).toContain('网络失败')
  })

  it('keeps automation rows out of ordinary hide-done and clear-done semantics', async () => {
    const store = useTodoStore()
    store.todos.push({
      id: automation.todoId,
      text: '旧自动化',
      category: 'automation',
      done: true,
      createdAt: '2026-08-14T00:00:00Z',
      recurrence: { frequency: 'none', interval: 1 },
    })
    store.automations.push(automation)
    store.hideDone = true

    expect(store.filteredTodos).toHaveLength(1)
    await store.clearDone()
    expect(api.apiDeleteAutomation).not.toHaveBeenCalled()
    expect(store.todos).toHaveLength(1)
  })

  it('does not publish a mixed todo and automation snapshot when refresh partially fails', async () => {
    const store = useTodoStore()
    store.todos.push({
      id: 'todo_old',
      text: '旧快照',
      category: 'task',
      done: false,
      createdAt: '2026-08-14T00:00:00Z',
      recurrence: { frequency: 'none', interval: 1 },
    })
    store.automations.push(automation)
    api.apiListTodos.mockResolvedValueOnce([{
      id: 'todo_new', text: '新快照', category: 'task', done: false, createdAt: '2026-08-14T01:00:00Z',
    }])
    api.apiListAutomations.mockRejectedValueOnce(new Error('自动化列表暂不可用'))

    expect(await store.refreshFromServer()).toBe(false)

    expect(store.todos.map((item) => item.id)).toEqual(['todo_old'])
    expect(store.automations.map((item) => item.id)).toEqual([automation.id])
  })

  it('keeps the newest refresh result when an older request finishes late', async () => {
    const store = useTodoStore()
    const firstTodos = deferred<TodoItemData[]>()
    const firstAutomations = deferred<typeof automation[]>()
    api.apiListTodos
      .mockImplementationOnce(() => firstTodos.promise)
      .mockResolvedValueOnce([{
        id: 'todo_latest', text: '最新', category: 'task', done: false, createdAt: '2026-08-14T02:00:00Z',
      }])
    api.apiListAutomations
      .mockImplementationOnce(() => firstAutomations.promise)
      .mockResolvedValueOnce([])

    const staleRefresh = store.refreshFromServer()
    await vi.waitFor(() => expect(api.apiListTodos).toHaveBeenCalledTimes(1))
    const latestRefresh = store.refreshFromServer()
    expect(await latestRefresh).toBe(true)
    firstTodos.resolve([{
      id: 'todo_stale', text: '旧响应', category: 'task', done: false, createdAt: '2026-08-14T01:00:00Z',
    }])
    firstAutomations.resolve([automation])
    expect(await staleRefresh).toBe(false)

    expect(store.todos.map((item) => item.id)).toEqual(['todo_latest'])
    expect(store.automations).toEqual([])
  })

  it('prevents duplicate pause requests while one item is pending', async () => {
    const pendingToggle = deferred<typeof automation>()
    api.apiToggleAutomation.mockImplementationOnce(() => pendingToggle.promise)
    const store = useTodoStore()
    store.todos.push({
      id: automation.todoId,
      text: '日报',
      category: 'automation',
      done: false,
      createdAt: '2026-08-14T00:00:00Z',
      recurrence: { frequency: 'none', interval: 1 },
    })
    store.automations.push(automation)

    const first = store.setAutomationEnabled(automation.todoId, false)
    const duplicate = store.setAutomationEnabled(automation.todoId, false)
    expect(await duplicate).toBe(false)
    pendingToggle.resolve({ ...automation, enabled: false })
    expect(await first).toBe(true)

    expect(api.apiToggleAutomation).toHaveBeenCalledTimes(1)
  })

  it('keeps ordinary todo deletion on the todo endpoint', async () => {
    const store = useTodoStore()
    store.todos.push({
      id: 'todo_regular',
      text: '普通待办',
      category: 'task',
      done: false,
      createdAt: '2026-08-14T00:00:00Z',
      recurrence: { frequency: 'none', interval: 1 },
    })

    expect(await store.removeTodo('todo_regular')).toBe(true)

    expect(api.apiDeleteTodo).toHaveBeenCalledWith('u1', 'todo_regular')
    expect(api.apiDeleteAutomation).not.toHaveBeenCalled()
  })
})
