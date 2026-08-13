/** State and polling lifecycle for the durable Agent task queue. */
import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { fetchQueue, type AgentQueueTask } from '@/api/agentQueue'

export const useAgentQueueStore = defineStore('agentQueue', () => {
  const tasks = ref<AgentQueueTask[]>([]), history = ref<AgentQueueTask[]>([]), maxConcurrency = ref(5), loading = ref(false)
  const pending = computed(() => tasks.value.filter(item => item.status === 'pending'))
  const running = computed(() => tasks.value.filter(item => item.status === 'running'))
  const review = computed(() => tasks.value.filter(item => item.status === 'review'))
  async function load(userId: string, isHistory = false) {
    if (!userId) return
    loading.value = true
    try { const result = await fetchQueue(userId, isHistory); maxConcurrency.value = result.settings.max_concurrency; if (isHistory) history.value = result.tasks; else tasks.value = result.tasks } finally { loading.value = false }
  }
  return { tasks, history, maxConcurrency, loading, pending, running, review, load }
})
