import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { createSessionTaskList, fetchSessionTaskList } from '@/api/taskList'
import type { AgentTaskList } from '@/api/taskList'

export const useTaskListStore = defineStore('taskList', () => {
  const taskList = ref<AgentTaskList | null>(null)
  const sidebarOpen = ref(false)
  const autoOpenOnUpdate = ref(true)
  const loading = ref(false)
  const error = ref('')

  const hasTaskList = computed(() => taskList.value !== null)
  const currentItem = computed(() => {
    const list = taskList.value
    if (!list?.current_item_id) return null
    return list.items.find((item) => item.id === list.current_item_id) ?? null
  })
  const completedCount = computed(() => {
    return taskList.value?.items.filter((item) => item.status === 'completed').length ?? 0
  })

  function setTaskList(next: AgentTaskList | null | undefined, options?: { open?: boolean }) {
    taskList.value = next ?? null
    const shouldOpen = options?.open ?? autoOpenOnUpdate.value
    if (taskList.value && shouldOpen) {
      sidebarOpen.value = true
    }
  }

  async function load(sessionId: string, options?: { open?: boolean }) {
    if (!sessionId) {
      clear()
      return
    }
    loading.value = true
    error.value = ''
    try {
      const response = await fetchSessionTaskList(sessionId)
      setTaskList(response.task_list, options)
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
      taskList.value = null
    } finally {
      loading.value = false
    }
  }

  async function create(sessionId: string, title: string, items: string[], options?: { open?: boolean }) {
    const cleaned = items.map((item) => item.trim()).filter(Boolean)
    if (!sessionId || cleaned.length === 0) return null
    loading.value = true
    error.value = ''
    try {
      const response = await createSessionTaskList(sessionId, title, cleaned)
      setTaskList(response.task_list, options)
      return response.task_list
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
      return null
    } finally {
      loading.value = false
    }
  }

  function clear() {
    taskList.value = null
    sidebarOpen.value = false
    error.value = ''
  }

  function setSidebarOpen(open: boolean) {
    sidebarOpen.value = open
  }

  function toggleSidebar() {
    sidebarOpen.value = !sidebarOpen.value
  }

  function setAutoOpenOnUpdate(open: boolean) {
    autoOpenOnUpdate.value = open
  }

  return {
    taskList,
    sidebarOpen,
    autoOpenOnUpdate,
    loading,
    error,
    hasTaskList,
    currentItem,
    completedCount,
    setTaskList,
    load,
    create,
    clear,
    setSidebarOpen,
    toggleSidebar,
    setAutoOpenOnUpdate,
  }
})
