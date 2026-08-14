/**
 * Todo sidebar automation-management interaction tests.
 *
 * Usage:
 * Mounts the real Pinia todo store with deterministic automation records, then
 * verifies the sidebar's automation-only controls, status copy, destructive
 * confirmation, validation, pending state, and accessible focus targets.
 */

import { nextTick } from 'vue'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import TodoSidebar from '../TodoSidebar.vue'
import { useTodoStore, type AutomationTask } from '@/stores/todo'

/** Mounted wrappers are tracked so each component interval is disposed. */
const mountedWrappers: VueWrapper[] = []

/** Creates one complete scheduler record with caller-selected lifecycle state. */
function createAutomation(overrides: Partial<AutomationTask> = {}): AutomationTask {
  return {
    id: 'automation-1',
    todoId: 'todo-automation-1',
    prompt: '整理当天工作并生成日报',
    timezone: 'Asia/Shanghai',
    recurrence: { frequency: 'daily', interval: 1 },
    nextRunAt: '2099-08-15T01:00:00.000Z',
    accessMode: 'sandbox',
    enabled: true,
    ...overrides,
  }
}

/** Adds the TODO shell paired with one automation definition. */
function seedAutomation(
  store: ReturnType<typeof useTodoStore>,
  automation: AutomationTask,
  text: string,
): void {
  store.todos.push({
    id: automation.todoId,
    text,
    category: 'automation',
    done: false,
    createdAt: '2026-08-14T00:00:00.000Z',
    recurrence: { frequency: 'none', interval: 1 },
  })
  store.automations.push(automation)
}

/** Mounts the sidebar without replacing the deterministic seeded state. */
function mountSidebar(store: ReturnType<typeof useTodoStore>): VueWrapper {
  vi.spyOn(store, 'refreshFromServer').mockResolvedValue(true)
  const wrapper = mount(TodoSidebar, {
    attachTo: document.body,
    global: {
      stubs: {
        IcIcon: { template: '<span class="icon-stub" aria-hidden="true" />' },
      },
    },
  })
  mountedWrappers.push(wrapper)
  return wrapper
}

describe('TodoSidebar automation management', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  afterEach(() => {
    mountedWrappers.splice(0).forEach((wrapper) => wrapper.unmount())
    document.body.innerHTML = ''
  })

  it('renders planned, paused, completed, and failed states without ordinary TODO controls', async () => {
    const store = useTodoStore()
    const planned = createAutomation({ id: 'planned', todoId: 'todo-planned' })
    const paused = createAutomation({ id: 'paused', todoId: 'todo-paused', enabled: false })
    const completed = createAutomation({
      id: 'completed',
      todoId: 'todo-completed',
      enabled: false,
      recurrence: { frequency: 'none', interval: 1 },
      lastRunAt: '2026-08-14T01:00:00.000Z',
      lastStatus: 'success',
    })
    const failed = createAutomation({
      id: 'failed',
      todoId: 'todo-failed',
      enabled: false,
      lastRunAt: '2026-08-14T02:00:00.000Z',
      lastStatus: 'failed',
      lastError: '模型额度不足',
    })
    seedAutomation(store, planned, '计划任务')
    seedAutomation(store, paused, '暂停任务')
    seedAutomation(store, completed, '完成任务')
    seedAutomation(store, failed, '失败任务')

    const wrapper = mountSidebar(store)

    expect(wrapper.text()).toContain('已启用')
    expect(wrapper.text()).toContain('已暂停')
    expect(wrapper.text()).toContain('已完成')
    expect(wrapper.text()).toContain('失败后暂停')
    expect(wrapper.findAll('.creative-checkbox')).toHaveLength(0)
    expect(wrapper.findAll('button[title="添加日期"]')).toHaveLength(0)

    const failedRow = wrapper.get('[data-todo-id="todo-failed"]')
    await failedRow.get('button[aria-label="展开自动化详情"]').trigger('click')
    expect(failedRow.text()).toContain('Asia/Shanghai')
    expect(failedRow.text()).toContain('失败')
    expect(failedRow.text()).toContain('模型额度不足')
  })

  it('pauses and resumes through accessible controls and disables them while pending', async () => {
    const store = useTodoStore()
    const automation = createAutomation()
    seedAutomation(store, automation, '日报')
    const setEnabled = vi.spyOn(store, 'setAutomationEnabled').mockResolvedValue(true)
    const wrapper = mountSidebar(store)
    const row = wrapper.get(`[data-todo-id="${automation.todoId}"]`)

    const pauseButton = row.get('button[aria-label="暂停自动化：日报"]')
    const pauseElement = pauseButton.element as HTMLButtonElement
    pauseElement.focus()
    expect(document.activeElement).toBe(pauseElement)
    await pauseButton.trigger('click')
    expect(setEnabled).toHaveBeenCalledWith(automation.todoId, false)

    store.automations[0] = { ...automation, enabled: false }
    await nextTick()
    await row.get('button[aria-label="恢复自动化：日报"]').trigger('click')
    expect(setEnabled).toHaveBeenLastCalledWith(automation.todoId, true)

    store.automationPendingIds = new Set([automation.todoId])
    await nextTick()
    expect(row.attributes('aria-busy')).toBe('true')
    expect(row.get('button[aria-label="恢复自动化：日报"]').attributes()).toHaveProperty('disabled')
    expect(row.get('button[aria-label="删除自动化：日报"]').attributes()).toHaveProperty('disabled')
  })

  it('requires explicit automation deletion confirmation and keeps failures visible', async () => {
    const store = useTodoStore()
    const automation = createAutomation()
    seedAutomation(store, automation, '日报')
    let resolveDeletion: ((deleted: boolean) => void) | undefined
    const removeTodo = vi.spyOn(store, 'removeTodo').mockImplementation(async (todoId) => {
      store.automationPendingIds = new Set([todoId])
      return await new Promise<boolean>((resolve) => {
        resolveDeletion = resolve
      })
    })
    const wrapper = mountSidebar(store)
    const row = wrapper.get(`[data-todo-id="${automation.todoId}"]`)

    await row.get('button[aria-label="删除自动化：日报"]').trigger('click')
    expect(removeTodo).not.toHaveBeenCalled()
    expect(row.text()).toContain('将取消未来执行并删除运行记录')

    await row.get('button[aria-label="取消删除自动化：日报"]').trigger('click')
    expect(row.text()).not.toContain('将取消未来执行并删除运行记录')

    await row.get('button[aria-label="删除自动化：日报"]').trigger('click')
    await row.get('button[aria-label="确认删除自动化：日报"]').trigger('click')
    await nextTick()

    expect(row.get('button[aria-label="确认删除自动化：日报"]').attributes()).toHaveProperty('disabled')
    expect(row.text()).toContain('正在取消')

    store.automationActionErrors = { [automation.todoId]: '删除自动化任务失败：数据库忙' }
    store.automationPendingIds = new Set()
    resolveDeletion?.(false)
    await flushPromises()

    expect(removeTodo).toHaveBeenCalledWith(automation.todoId)
    expect(wrapper.find(`[data-todo-id="${automation.todoId}"]`).exists()).toBe(true)
    expect(row.get('[role="alert"]').text()).toContain('数据库忙')
  })

  it('validates future execution time and explains timezone and full-access risk', async () => {
    const store = useTodoStore()
    const addAutomation = vi.spyOn(store, 'addAutomation').mockResolvedValue({ success: true })
    const wrapper = mountSidebar(store)

    await wrapper.get('button[aria-label="新建自动化任务"]').trigger('click')
    const form = wrapper.get('form.todo-automation-form')
    expect(form.text()).toContain(`任务时区：${Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'}`)

    await form.get('input[aria-label="自动化任务名称"]').setValue('日报')
    await form.get('textarea[aria-label="自动化执行指令"]').setValue('生成日报')
    await form.get('input[aria-label="首次执行时间"]').setValue('2000-01-01T00:00')
    await form.trigger('submit')
    expect(addAutomation).not.toHaveBeenCalled()
    expect(form.get('[role="alert"]').text()).toContain('晚于当前时间')

    await form.get('select[aria-label="运行权限"]').setValue('full_access')
    expect(form.get('[role="note"]').text()).toContain('完全访问权限')

    await form.get('input[aria-label="首次执行时间"]').setValue('2099-08-15T09:00')
    await form.trigger('submit')
    await flushPromises()

    expect(addAutomation).toHaveBeenCalledWith(
      '日报',
      '生成日报',
      new Date('2099-08-15T09:00').toISOString(),
      Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC',
      { frequency: 'none', interval: 1 },
      'full_access',
    )
  })

  it('preserves ordinary TODO checkbox and date controls', () => {
    const store = useTodoStore()
    store.todos.push({
      id: 'todo-ordinary',
      text: '普通待办',
      category: 'task',
      done: false,
      createdAt: '2026-08-14T00:00:00.000Z',
      recurrence: { frequency: 'none', interval: 1 },
    })

    const wrapper = mountSidebar(store)
    const row = wrapper.get('[data-todo-id="todo-ordinary"]')

    expect(row.find('.creative-checkbox').exists()).toBe(true)
    expect(row.find('button[aria-label="添加任务日期：普通待办"]').exists()).toBe(true)
    expect(row.find('button[aria-label^="暂停自动化"]').exists()).toBe(false)
  })
})
