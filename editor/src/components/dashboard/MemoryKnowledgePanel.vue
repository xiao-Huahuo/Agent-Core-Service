<!--
  MemoryKnowledgePanel —— 长期记忆与知识库召回观测页。
-->

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { fetchRecallDetails } from '@/api/agent'
import {
  addMemory,
  addSystemPromptEntry,
  deleteMemory,
  deleteSystemPromptEntry,
  fetchMemories,
  fetchSystemPrompts,
} from '@/api/settings'
import type { MemoryEntry, SystemPromptEntry } from '@/api/settings'
import { useSettingsStore } from '@/stores/settings'
import { useSessionStore } from '@/stores/session'
import { useChatStore } from '@/stores/chat'
import InjectedEntriesCard from '@/components/dashboard/InjectedEntriesCard.vue'
import LongTermMemoryCard from '@/components/dashboard/LongTermMemoryCard.vue'
import KnowledgeRecallCard from '@/components/dashboard/KnowledgeRecallCard.vue'

const settingsStore = useSettingsStore()
const sessionStore = useSessionStore()
const chatStore = useChatStore()

/** 记忆召回条目 */
interface MemoryRecallItem {
  memory_id?: string
  memory_type?: string
  content?: string
  merged_score?: number
  final_score?: number
  vector_score?: number
  keyword_score?: number
  rerank_score?: number
  retrieval_channels?: string[]
  matched_terms?: string[]
}

/** 知识召回条目 */
interface KnowledgeRecallItem {
  memory_id?: string
  memory_type?: string
  content?: string
  merged_score?: number
  final_score?: number
  vector_score?: number
  keyword_score?: number
  rerank_score?: number
  retrieval_channels?: string[]
  matched_terms?: string[]
}

/** 召回快照 */
interface RecallPayload {
  session_id: string
  user_id: string
  created_at: string
  query: string
  rag_metrics: Record<string, unknown>
  memory_recall: { pre_rerank: MemoryRecallItem[]; post_rerank: MemoryRecallItem[] }
  knowledge_recall: { pre_rerank: KnowledgeRecallItem[]; post_rerank: KnowledgeRecallItem[] }
}

function createEmptyRecallPayload(): RecallPayload {
  return {
    session_id: '',
    user_id: '',
    created_at: '',
    query: '',
    rag_metrics: {},
    memory_recall: { pre_rerank: [], post_rerank: [] },
    knowledge_recall: { pre_rerank: [], post_rerank: [] },
  }
}

const recallPayload = ref<RecallPayload>(createEmptyRecallPayload())
const isRecallLoading = ref(false)
const promptEntries = ref<SystemPromptEntry[]>([])
const memories = ref<MemoryEntry[]>([])
const newPromptContent = ref('')
const newMemoryContent = ref('')
const isInjectionLoading = ref(false)
const addingPrompt = ref(false)
const addingMemory = ref(false)
const promptMsg = ref('')
const memoryMsg = ref('')

const userId = computed(() => settingsStore.profile.userId)
const promptInjectionEntries = computed(() => promptEntries.value.map((entry) => ({
  id: entry.prompt_id,
  content: entry.content,
})))
const memoryInjectionEntries = computed(() => memories.value.map((entry) => ({
  id: entry.memory_id,
  content: entry.content,
})))

const recallRefreshKey = computed(() => {
  const lastAssistant = [...chatStore.messages].reverse().find((message) => message.role === 'assistant')
  return [
    sessionStore.currentSessionId || '',
    chatStore.loadedSessionId || '',
    chatStore.isStreaming ? 'streaming' : 'idle',
    lastAssistant?.message_id || lastAssistant?.created_at || '',
    chatStore.messages.length,
  ].join(':')
})

async function loadRecallPayload(): Promise<void> {
  const sessionId = sessionStore.currentSessionId
  if (!userId.value || !sessionId) {
    recallPayload.value = createEmptyRecallPayload()
    return
  }
  if (chatStore.isStreaming) {
    return
  }

  isRecallLoading.value = true
  try {
    const result = await fetchRecallDetails(sessionId, userId.value)
    recallPayload.value = result as unknown as RecallPayload
  } catch (error) {
    console.error('加载召回快照失败:', error)
    recallPayload.value = createEmptyRecallPayload()
  } finally {
    isRecallLoading.value = false
  }
}

function showMessage(target: typeof promptMsg, text: string, duration = 2000): void {
  target.value = text
  window.setTimeout(() => {
    if (target.value === text) {
      target.value = ''
    }
  }, duration)
}

async function loadInjectedEntries(): Promise<void> {
  if (!userId.value) {
    promptEntries.value = []
    memories.value = []
    return
  }

  isInjectionLoading.value = true
  try {
    const [promptRes, memoryRes] = await Promise.all([
      fetchSystemPrompts(userId.value),
      fetchMemories(userId.value),
    ])
    promptEntries.value = promptRes.entries ?? []
    memories.value = memoryRes ?? []
  } catch (error) {
    console.error('加载长期注入内容失败:', error)
    showMessage(promptMsg, '加载失败')
  } finally {
    isInjectionLoading.value = false
  }
}

async function handleAddPrompt(): Promise<void> {
  const content = newPromptContent.value.trim()
  if (!content || !userId.value) return
  addingPrompt.value = true
  try {
    await addSystemPromptEntry(userId.value, content)
    newPromptContent.value = ''
    await loadInjectedEntries()
    showMessage(promptMsg, '已添加')
  } catch {
    showMessage(promptMsg, '添加失败')
  } finally {
    addingPrompt.value = false
  }
}

async function handleDeletePrompt(promptId: string): Promise<void> {
  try {
    await deleteSystemPromptEntry(promptId)
    await loadInjectedEntries()
    showMessage(promptMsg, '已删除')
  } catch {
    showMessage(promptMsg, '删除失败')
  }
}

async function handleAddMemory(): Promise<void> {
  const content = newMemoryContent.value.trim()
  if (!content || !userId.value) return
  addingMemory.value = true
  try {
    await addMemory(userId.value, content)
    newMemoryContent.value = ''
    await loadInjectedEntries()
    showMessage(memoryMsg, '已添加')
  } catch {
    showMessage(memoryMsg, '添加失败')
  } finally {
    addingMemory.value = false
  }
}

async function handleDeleteMemory(memoryId: string): Promise<void> {
  try {
    await deleteMemory(memoryId)
    await loadInjectedEntries()
    showMessage(memoryMsg, '已删除')
  } catch {
    showMessage(memoryMsg, '删除失败')
  }
}

watch(
  () => [userId.value, sessionStore.currentSessionId, recallRefreshKey.value],
  () => {
    loadRecallPayload()
  },
  { immediate: true },
)

watch(
  () => userId.value,
  () => {
    loadInjectedEntries()
  },
  { immediate: true },
)
</script>

<template>
  <div class="mk-panel">
    <div class="memory-knowledge-layout">
      <KnowledgeRecallCard
        class="knowledge-card"
        :recall-snapshot="recallPayload.knowledge_recall"
        :is-loading="isRecallLoading"
      />
      <div class="memory-column">
        <LongTermMemoryCard
          class="memory-recall-card"
          :recall-snapshot="recallPayload.memory_recall"
          :is-loading="isRecallLoading"
        />
        <div class="injection-grid">
          <InjectedEntriesCard
            v-model:new-content="newPromptContent"
            title="长期规则注入"
            placeholder="输入长期规则"
            empty-text="暂无长期规则注入"
            :entries="promptInjectionEntries"
            :is-adding="addingPrompt"
            :is-loading="isInjectionLoading"
            :message="promptMsg"
            @add="handleAddPrompt"
            @delete="handleDeletePrompt"
          />
          <InjectedEntriesCard
            v-model:new-content="newMemoryContent"
            title="长期记忆注入"
            placeholder="输入长期记忆"
            empty-text="暂无长期记忆注入"
            :entries="memoryInjectionEntries"
            :is-adding="addingMemory"
            :is-loading="isInjectionLoading"
            :message="memoryMsg"
            @add="handleAddMemory"
            @delete="handleDeleteMemory"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.mk-panel {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  overflow: hidden;
  padding: var(--space-10);
}

.memory-knowledge-layout {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-10);
  flex: 1;
  min-height: 0;
}

.knowledge-card,
.memory-column,
.memory-recall-card,
.injection-grid > * {
  height: 100%;
  width: 100%;
  min-width: 0;
  min-height: 0;
}

.memory-column {
  display: grid;
  grid-template-rows: minmax(0, 1fr) minmax(0, 1fr);
  gap: var(--space-10);
}

.injection-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-10);
  min-height: 0;
}

.mk-panel :deep(.card-block) {
  box-shadow: none;
}

@media (max-width: 1200px) {
  .memory-knowledge-layout {
    grid-template-columns: minmax(0, 0.9fr) minmax(0, 1.1fr);
  }

  .injection-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .mk-panel {
    flex: none;
    overflow: visible;
    padding: var(--space-8);
  }

  .memory-knowledge-layout,
  .memory-column,
  .injection-grid {
    display: flex;
    flex-direction: column;
  }

  .knowledge-card,
  .memory-recall-card,
  .injection-grid > * {
    height: 320px;
    flex: none;
  }
}

@media (max-width: 560px) {
  .mk-panel {
    gap: var(--space-8);
    padding: var(--space-8) var(--space-6);
  }
}
</style>
