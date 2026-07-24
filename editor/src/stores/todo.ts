/*
 * Todo list store.
 *
 * Usage:
 * Owns the todo list state for the right-side todo sidebar. Todos are stored
 * in localStorage so they survive page reloads without backend dependencies.
 */

import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

export interface TodoItem {
  id: string
  text: string
  done: boolean
  createdAt: string
  dueDate?: string
}

const STORAGE_KEY = 'metaweave_todos'

function createId(): string {
  return `todo_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`
}

function loadTodos(): TodoItem[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    return JSON.parse(raw) as TodoItem[]
  } catch {
    return []
  }
}

function saveTodos(todos: TodoItem[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(todos))
  } catch {
    // ignore storage quota errors
  }
}

export const useTodoStore = defineStore('todo', () => {
  const todos = ref<TodoItem[]>(loadTodos())
  const hideDone = ref(false)
  const searchQuery = ref('')
  const todoSidebarSplitRatio = ref(0.5)

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

  function persist() {
    saveTodos(todos.value)
  }

  function addTodo(text: string, dueDate?: string) {
    const trimmed = text.trim()
    if (!trimmed) return
    todos.value.unshift({
      id: createId(),
      text: trimmed,
      done: false,
      createdAt: new Date().toISOString(),
      dueDate: dueDate || undefined,
    })
    persist()
  }

  function toggleTodo(id: string) {
    const item = todos.value.find((t) => t.id === id)
    if (!item) return
    item.done = !item.done
    persist()
  }

  function removeTodo(id: string) {
    todos.value = todos.value.filter((t) => t.id !== id)
    persist()
  }

  function editTodo(id: string, text: string) {
    const trimmed = text.trim()
    if (!trimmed) return
    const item = todos.value.find((t) => t.id === id)
    if (!item) return
    item.text = trimmed
    persist()
  }

  function setDueDate(id: string, dueDate?: string) {
    const item = todos.value.find((t) => t.id === id)
    if (!item) return
    item.dueDate = dueDate || undefined
    persist()
  }

  function toggleHideDone() {
    hideDone.value = !hideDone.value
  }

  function clearDone() {
    todos.value = todos.value.filter((t) => !t.done)
    persist()
  }

  // Expose for split-ratio persistence (saved in EditorWorkspace)
  function setSplitRatio(ratio: number) {
    todoSidebarSplitRatio.value = Math.max(0.1, Math.min(0.9, ratio))
  }

  return {
    todos,
    hideDone,
    searchQuery,
    todoSidebarSplitRatio,
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
  }
})
