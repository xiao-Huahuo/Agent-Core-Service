/*
 * Todo list store — 前后端双向同步。
 *
 * Usage:
 * 所有增删改操作乐观更新本地状态后立即调用后端 API。
 * 后端失败时回滚并显示错误。
 */

import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { apiAddTodo, apiDeleteTodo, apiEditTodo, apiListTodos, apiToggleTodo } from '@/api/todo'
import type { TodoItemData } from '@/api/todo'
import {
  apiAddAutomation,
  apiDeleteAutomation,
  apiListAutomations,
  apiToggleAutomation,
} from '@/api/automation'
import type { AutomationTaskData } from '@/api/automation'

export interface TodoItem {
  id: string
  text: string
  category: string
  done: boolean
  createdAt: string
  updatedAt?: string
  dueDate?: string
  reminderAt?: string
  recurrence: { frequency: 'none' | 'daily' | 'weekly' | 'monthly'; interval: number }
  lastCompletedAt?: string
}

export type AutomationTask = AutomationTaskData

function toItem(data: TodoItemData): TodoItem {
  return {
    id: data.id ?? '',
    text: data.text ?? '',
    category: data.category ?? 'task',
    done: data.done ?? false,
    createdAt: data.createdAt ?? new Date().toISOString(),
    updatedAt: data.updatedAt,
    dueDate: data.dueDate || undefined,
    reminderAt: data.reminderAt || undefined,
    recurrence: data.recurrence ?? { frequency: 'none', interval: 1 },
    lastCompletedAt: data.lastCompletedAt || undefined,
  }
}

/** 等待中的后端操作队列（用于禁用 UI） */
type PendingOp = 'refresh' | 'add' | 'toggle' | 'edit' | 'delete' | 'clear'

export const useTodoStore = defineStore('todo', () => {
  const todos = ref<TodoItem[]>([])
  const automations = ref<AutomationTask[]>([])
  const hideDone = ref(false)
  const searchQuery = ref('')
  const todoSidebarSplitRatio = ref(0.5)
  const pending = ref<Set<PendingOp>>(new Set())
  const automationPendingIds = ref<Set<string>>(new Set())
  const automationActionErrors = ref<Record<string, string>>({})
  let refreshSequence = 0

  const overdueIds = computed(() => {
    const now = Date.now()
    const ids = new Set<string>()
    for (const item of todos.value) {
      if (!item.done && item.dueDate && new Date(item.dueDate).getTime() < now) {
        ids.add(item.id)
      }
    }
    return ids
  })

  const filteredTodos = computed(() => {
    let list = todos.value
    if (hideDone.value) {
      list = list.filter((item) => item.category === 'automation' || !item.done)
    }
    if (searchQuery.value.trim()) {
      const q = searchQuery.value.trim().toLowerCase()
      list = list.filter((item) => item.text.toLowerCase().includes(q))
    }
    return [...list].sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
  })

  const pendingCount = computed(() => todos.value.filter((item) => item.category !== 'automation' && !item.done).length)

  function automationForTodo(todoId: string): AutomationTask | undefined {
    return automations.value.find((item) => item.todoId === todoId)
  }

  function setAutomationPending(todoId: string, value: boolean): void {
    const next = new Set(automationPendingIds.value)
    if (value) next.add(todoId)
    else next.delete(todoId)
    automationPendingIds.value = next
  }

  function setAutomationError(todoId: string, message = ''): void {
    const next = { ...automationActionErrors.value }
    if (message) next[todoId] = message
    else delete next[todoId]
    automationActionErrors.value = next
  }

  async function refreshFromServer(): Promise<boolean> {
    const { useSettingsStore } = await import('@/stores/settings')
    const userId = useSettingsStore().profile.userId
    if (!userId) return false
    const sequence = ++refreshSequence
    pending.value = new Set([...pending.value, 'refresh'] as PendingOp[])
    try {
      const [serverTodos, serverAutomations] = await Promise.all([
        apiListTodos(userId),
        apiListAutomations(userId),
      ])
      if (sequence !== refreshSequence) return false
      todos.value = serverTodos.map(toItem)
      automations.value = serverAutomations
      return true
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      console.warn('[TodoStore] 从服务器刷新待办失败:', msg)
      return false
    } finally {
      if (sequence === refreshSequence) {
        pending.value = new Set([...pending.value].filter((p) => p !== 'refresh'))
      }
    }
  }

  async function addAutomation(
    text: string,
    prompt: string,
    nextRunAt: string,
    timezone: string,
    recurrence: AutomationTask['recurrence'],
    accessMode: AutomationTask['accessMode'],
  ): Promise<{ success: boolean; error?: string }> {
    const { useSettingsStore } = await import('@/stores/settings')
    const userId = useSettingsStore().profile.userId
    if (!userId) return { success: false, error: '当前没有登录用户。' }
    try {
      const automation = await apiAddAutomation(userId, text, prompt, nextRunAt, timezone, recurrence, accessMode)
      automations.value = [...automations.value, automation]
      todos.value = [{
        id: automation.todoId,
        text,
        category: 'automation',
        done: false,
        createdAt: new Date().toISOString(),
        recurrence: { frequency: 'none', interval: 1 },
      }, ...todos.value]
      await refreshFromServer()
      return { success: true }
    } catch (e) {
      const error = e instanceof Error ? e.message : String(e)
      console.warn('[TodoStore] 创建自动化任务失败:', error)
      return { success: false, error }
    }
  }

  async function addTodo(text: string, dueDate?: string, reminderAt?: string, recurrence?: TodoItem['recurrence']) {
    const trimmed = text.trim()
    if (!trimmed) return
    const { useSettingsStore } = await import('@/stores/settings')
    const userId = useSettingsStore().profile.userId
    if (!userId) return

    // 乐观创建本地项
    const localId = `todo_opt_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`
    const item: TodoItem = {
      id: localId,
      text: trimmed,
      category: 'task',
      done: false,
      createdAt: new Date().toISOString(),
      dueDate: dueDate || undefined,
      reminderAt: reminderAt || undefined,
      recurrence: recurrence ?? { frequency: 'none', interval: 1 },
    }
    todos.value.unshift(item)

    pending.value = new Set([...pending.value, 'add'])
    try {
      const serverItem = await apiAddTodo(userId, trimmed, dueDate, reminderAt, recurrence)
      const idx = todos.value.findIndex((t) => t.id === localId)
      if (idx !== -1) {
        todos.value[idx] = toItem(serverItem)
      }
    } catch (e) {
      // 回滚
      todos.value = todos.value.filter((t) => t.id !== localId)
      const msg = e instanceof Error ? e.message : String(e)
      console.warn('[TodoStore] 添加待办失败:', msg)
    } finally {
      pending.value = new Set([...pending.value].filter((p) => p !== 'add'))
    }
  }

  async function toggleTodo(id: string) {
    const { useSettingsStore } = await import('@/stores/settings')
    const userId = useSettingsStore().profile.userId
    if (!userId) return

    const automation = automationForTodo(id)
    const todo = todos.value.find((item) => item.id === id)
    if (todo?.category === 'automation' && !automation) {
      setAutomationError(id, '自动化元数据尚未加载，请刷新后重试。')
      return
    }
    if (automation) {
      await setAutomationEnabled(id, !automation.enabled)
      return
    }

    // 乐观更新
    const idx = todos.value.findIndex((t) => t.id === id)
    if (idx === -1) return
    const item = todos.value[idx]!
    const prev = { ...item }
    todos.value[idx] = { ...item, done: !item.done }

    pending.value = new Set([...pending.value, 'toggle'])
    try {
      const serverItem = await apiToggleTodo(userId, id)
      const currentIndex = todos.value.findIndex((item) => item.id === id)
      if (currentIndex !== -1) todos.value[currentIndex] = toItem(serverItem)
    } catch (e) {
      // 回滚
      const currentIndex = todos.value.findIndex((item) => item.id === id)
      if (currentIndex !== -1) todos.value[currentIndex] = prev
      const msg = e instanceof Error ? e.message : String(e)
      console.warn('[TodoStore] 切换待办状态失败:', msg)
    } finally {
      pending.value = new Set([...pending.value].filter((p) => p !== 'toggle'))
    }
  }

  async function setAutomationEnabled(todoId: string, enabled: boolean): Promise<boolean> {
    const { useSettingsStore } = await import('@/stores/settings')
    const userId = useSettingsStore().profile.userId
    const automation = automationForTodo(todoId)
    if (!userId || !automation || automationPendingIds.value.has(todoId)) return false

    const previous = automation
    setAutomationPending(todoId, true)
    setAutomationError(todoId)
    automations.value = automations.value.map((item) => (
      item.id === automation.id ? { ...item, enabled } : item
    ))
    try {
      const updated = await apiToggleAutomation(userId, automation.id, enabled)
      automations.value = automations.value.map((item) => item.id === updated.id ? updated : item)
      return true
    } catch (e) {
      automations.value = automations.value.map((item) => (
        item.id === previous.id ? { ...item, enabled: previous.enabled } : item
      ))
      const message = e instanceof Error ? e.message : String(e)
      setAutomationError(todoId, `更新自动化状态失败：${message}`)
      console.warn('[TodoStore] 更新自动化状态失败:', message)
      return false
    } finally {
      setAutomationPending(todoId, false)
    }
  }

  async function removeTodo(id: string): Promise<boolean> {
    const { useSettingsStore } = await import('@/stores/settings')
    const userId = useSettingsStore().profile.userId
    if (!userId) return false

    const idx = todos.value.findIndex((t) => t.id === id)
    if (idx === -1) return false
    const automation = automationForTodo(id)
    if (todos.value[idx]?.category === 'automation' && !automation) {
      setAutomationError(id, '自动化元数据尚未加载，已阻止不完整删除；请刷新后重试。')
      return false
    }
    if (automation) {
      if (automationPendingIds.value.has(id)) return false
      setAutomationPending(id, true)
      setAutomationError(id)
      try {
        await apiDeleteAutomation(userId, automation.id)
        todos.value = todos.value.filter((item) => item.id !== id)
        automations.value = automations.value.filter((item) => item.id !== automation.id)
        return true
      } catch (e) {
        const message = e instanceof Error ? e.message : String(e)
        setAutomationError(id, `删除自动化任务失败：${message}`)
        console.warn('[TodoStore] 删除自动化任务失败:', message)
        return false
      } finally {
        setAutomationPending(id, false)
      }
    }

    // 普通 TODO 保留原有乐观删除与失败回滚。
    const removed = todos.value.splice(idx, 1)[0]!

    pending.value = new Set([...pending.value, 'delete'])
    try {
      await apiDeleteTodo(userId, id)
      return true
    } catch (e) {
      // 回滚 — 恢复到原位
      todos.value.splice(idx, 0, removed)
      const msg = e instanceof Error ? e.message : String(e)
      console.warn('[TodoStore] 删除待办失败:', msg)
      return false
    } finally {
      pending.value = new Set([...pending.value].filter((p) => p !== 'delete'))
    }
  }

  async function editTodo(id: string, text: string, dueDate?: string, reminderAt?: string, recurrence?: TodoItem['recurrence']) {
    const trimmed = text.trim()
    if (!trimmed) return
    const { useSettingsStore } = await import('@/stores/settings')
    const userId = useSettingsStore().profile.userId
    if (!userId) return

    const idx = todos.value.findIndex((t) => t.id === id)
    if (idx === -1) return
    const item = todos.value[idx]!
    const prev = { ...item }
    todos.value[idx] = { ...item, text: trimmed }

    pending.value = new Set([...pending.value, 'edit'])
    try {
      const serverItem = await apiEditTodo(userId, id, trimmed, dueDate, reminderAt, recurrence)
      const currentIndex = todos.value.findIndex((item) => item.id === id)
      if (currentIndex !== -1) todos.value[currentIndex] = toItem(serverItem)
    } catch (e) {
      const currentIndex = todos.value.findIndex((item) => item.id === id)
      if (currentIndex !== -1) todos.value[currentIndex] = prev
      const msg = e instanceof Error ? e.message : String(e)
      console.warn('[TodoStore] 编辑待办失败:', msg)
    } finally {
      pending.value = new Set([...pending.value].filter((p) => p !== 'edit'))
    }
  }

  async function setDueDate(id: string, dueDate?: string) {
    const { useSettingsStore } = await import('@/stores/settings')
    const userId = useSettingsStore().profile.userId
    if (!userId) return
    if (todos.value.find((item) => item.id === id)?.category === 'automation') {
      setAutomationError(id, '自动化执行时间需要通过自动化详情修改。')
      return
    }

    const idx = todos.value.findIndex((t) => t.id === id)
    if (idx === -1) return
    const item = todos.value[idx]!
    const prev = { ...item }
    const newDueDate = dueDate || undefined
    todos.value[idx] = { ...item, dueDate: newDueDate }

    // 后端没有单独的 setDueDate API，用 edit 把当前 text 一并提交
    pending.value = new Set([...pending.value, 'edit'])
    try {
      const serverItem = await apiEditTodo(userId, id, prev.text, dueDate, prev.reminderAt, prev.recurrence)
      const currentIndex = todos.value.findIndex((item) => item.id === id)
      if (currentIndex !== -1) todos.value[currentIndex] = toItem(serverItem)
    } catch (e) {
      const currentIndex = todos.value.findIndex((item) => item.id === id)
      if (currentIndex !== -1) todos.value[currentIndex] = prev
      const msg = e instanceof Error ? e.message : String(e)
      console.warn('[TodoStore] 设置截止日期失败:', msg)
    } finally {
      pending.value = new Set([...pending.value].filter((p) => p !== 'edit'))
    }
  }

  function toggleHideDone() {
    hideDone.value = !hideDone.value
  }

  async function clearDone() {
    const { useSettingsStore } = await import('@/stores/settings')
    const userId = useSettingsStore().profile.userId
    if (!userId) return

    const doneItems = todos.value.filter((t) => t.category !== 'automation' && t.done)
    if (doneItems.length === 0) return

    pending.value = new Set([...pending.value, 'clear'])
    try {
      await Promise.all(doneItems.map((item) => removeTodo(item.id)))
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      console.warn('[TodoStore] 清除已完成待办失败:', msg)
    } finally {
      pending.value = new Set([...pending.value].filter((p) => p !== 'clear'))
    }
  }

  function setSplitRatio(ratio: number) {
    todoSidebarSplitRatio.value = Math.max(0.1, Math.min(0.9, ratio))
  }

  return {
    todos,
    automations,
    automationPendingIds,
    automationActionErrors,
    hideDone,
    searchQuery,
    todoSidebarSplitRatio,
    pending,
    overdueIds,
    filteredTodos,
    pendingCount,
    addTodo,
    addAutomation,
    setAutomationEnabled,
    toggleTodo,
    removeTodo,
    editTodo,
    setDueDate,
    toggleHideDone,
    clearDone,
    setSplitRatio,
    refreshFromServer,
  }
})
