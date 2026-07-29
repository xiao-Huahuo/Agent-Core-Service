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
  const eventSerial = ref(0)
  const lastEventType = ref<'created' | 'updated' | 'completed' | 'cleared'>('cleared')

  const hasTaskList = computed(() => taskList.value !== null)
  const currentItem = computed(() => {
    const list = taskList.value
    if (!list?.current_item_id) return null
    return list.items.find((item) => item.id === list.current_item_id) ?? null
  })
  const completedCount = computed(() => {
    return taskList.value?.items.filter((item) => item.status === 'completed').length ?? 0
  })

  function setTaskList(next: AgentTaskList | null | undefined, options?: { open?: boolean; emitEvent?: boolean }) {
    const previous = taskList.value
    taskList.value = next ?? null
    const shouldEmitEvent = options?.emitEvent ?? true
    if (shouldEmitEvent) {
      eventSerial.value += 1
      if (!taskList.value) {
        lastEventType.value = 'cleared'
      } else if (taskList.value.status === 'completed') {
        lastEventType.value = 'completed'
      } else if (!previous || previous.task_list_id !== taskList.value.task_list_id) {
        lastEventType.value = 'created'
      } else {
        lastEventType.value = 'updated'
      }
    }
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
      setTaskList(response.task_list, { ...options, emitEvent: false })
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
    eventSerial.value += 1
    lastEventType.value = 'cleared'
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
    eventSerial,
    lastEventType,
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
