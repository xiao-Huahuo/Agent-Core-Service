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
type PendingOp = 'add' | 'toggle' | 'edit' | 'delete' | 'clear'

export const useTodoStore = defineStore('todo', () => {
  const todos = ref<TodoItem[]>([])
  const hideDone = ref(false)
  const searchQuery = ref('')
  const todoSidebarSplitRatio = ref(0.5)
  const pending = ref<Set<PendingOp>>(new Set())

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
      list = list.filter((item) => !item.done)
    }
    if (searchQuery.value.trim()) {
      const q = searchQuery.value.trim().toLowerCase()
      list = list.filter((item) => item.text.toLowerCase().includes(q))
    }
    return [...list].sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
  })

  const pendingCount = computed(() => todos.value.filter((item) => !item.done).length)

  async function refreshFromServer() {
    const { useSettingsStore } = await import('@/stores/settings')
    const userId = useSettingsStore().profile.userId
    if (!userId) return
    pending.value = new Set([...pending.value, 'add'] as PendingOp[])
    try {
      const serverTodos = await apiListTodos(userId)
      todos.value = serverTodos.map(toItem)
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      console.warn('[TodoStore] 从服务器刷新待办失败:', msg)
    } finally {
      pending.value = new Set([...pending.value].filter((p) => p !== 'add'))
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

    // 乐观更新
    const idx = todos.value.findIndex((t) => t.id === id)
    if (idx === -1) return
    const item = todos.value[idx]!
    const prev = { ...item }
    todos.value[idx] = { ...item, done: !item.done }

    pending.value = new Set([...pending.value, 'toggle'])
    try {
      const serverItem = await apiToggleTodo(userId, id)
      todos.value[idx] = toItem(serverItem)
    } catch (e) {
      // 回滚
      todos.value[idx] = prev
      const msg = e instanceof Error ? e.message : String(e)
      console.warn('[TodoStore] 切换待办状态失败:', msg)
    } finally {
      pending.value = new Set([...pending.value].filter((p) => p !== 'toggle'))
    }
  }

  async function removeTodo(id: string) {
    const { useSettingsStore } = await import('@/stores/settings')
    const userId = useSettingsStore().profile.userId
    if (!userId) return

    // 乐观删除
    const idx = todos.value.findIndex((t) => t.id === id)
    if (idx === -1) return
    const removed = todos.value.splice(idx, 1)[0]!

    pending.value = new Set([...pending.value, 'delete'])
    try {
      await apiDeleteTodo(userId, id)
    } catch (e) {
      // 回滚 — 恢复到原位
      todos.value.splice(idx, 0, removed)
      const msg = e instanceof Error ? e.message : String(e)
      console.warn('[TodoStore] 删除待办失败:', msg)
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
      todos.value[idx] = toItem(serverItem)
    } catch (e) {
      todos.value[idx] = prev
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
      todos.value[idx] = toItem(serverItem)
    } catch (e) {
      todos.value[idx] = prev
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

    const doneItems = todos.value.filter((t) => t.done)
    if (doneItems.length === 0) return

    pending.value = new Set([...pending.value, 'clear'])
    try {
      await Promise.all(doneItems.map((item) => apiDeleteTodo(userId, item.id)))
      todos.value = todos.value.filter((t) => !t.done)
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
    hideDone,
    searchQuery,
    todoSidebarSplitRatio,
    pending,
    overdueIds,
    filteredTodos,
    pendingCount,
    addTodo,
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
