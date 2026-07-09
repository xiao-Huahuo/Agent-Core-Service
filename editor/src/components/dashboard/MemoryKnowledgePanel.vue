<!--
  记忆与知识机制观测面板 — 双层不对称布局容器。
  上层: RagMetricsCard + TokenUsageCard
  下层: LongTermMemoryCard + KnowledgeRecallCard + LatencyCard
-->

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { fetchRecallDetails } from '@/api/agent'
import { useSettingsStore } from '@/stores/settings'
import { useSessionStore } from '@/stores/session'
import { useChatStore } from '@/stores/chat'
import RagMetricsCard from '@/components/dashboard/RagMetricsCard.vue'
import TokenUsageCard from '@/components/dashboard/TokenUsageCard.vue'
import LongTermMemoryCard from '@/components/dashboard/LongTermMemoryCard.vue'
import KnowledgeRecallCard from '@/components/dashboard/KnowledgeRecallCard.vue'
import LatencyCard from '@/components/dashboard/LatencyCard.vue'

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

const userId = computed(() => settingsStore.profile.userId)

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

watch(
  () => [userId.value, sessionStore.currentSessionId, recallRefreshKey.value],
  () => {
    loadRecallPayload()
  },
  { immediate: true },
)
</script>

<template>
  <div class="mk-panel">
    <div class="row-upper">
      <div class="col-rag">
        <RagMetricsCard />
      </div>
      <div class="col-token">
        <TokenUsageCard />
      </div>
    </div>
    <div class="row-lower">
      <div class="col-memory">
        <LongTermMemoryCard
          :recall-snapshot="recallPayload.memory_recall"
          :is-loading="isRecallLoading"
        />
      </div>
      <div class="col-knowledge">
        <KnowledgeRecallCard
          :recall-snapshot="recallPayload.knowledge_recall"
          :is-loading="isRecallLoading"
        />
      </div>
      <div class="col-latency">
        <LatencyCard />
      </div>
    </div>
  </div>
</template>

<style scoped>
.mk-panel {
  display: flex;
  flex-direction: column;
  gap: var(--space-10);
  flex: 1;
  min-height: 0;
  overflow: hidden;
  padding: var(--space-10);
}

.row-upper {
  display: flex;
  gap: var(--space-10);
  min-height: 0;
  height: 240px;
  align-items: stretch;
}

.row-lower {
  display: grid;
  grid-template-columns: minmax(280px, 1fr) minmax(280px, 1fr) minmax(0, 1fr);
  gap: var(--space-10);
  flex: 1;
  min-height: 0;
}

.col-rag {
  flex: 0 0 auto;
  min-width: 200px;
  max-width: 340px;
  min-height: 0;
}

.col-rag > * {
  height: 100%;
}

.col-token {
  width: 100%;
  flex: 1;
  min-width: 0;
  min-height: 0;
}

.col-memory {
  width: 100%;
  min-width: 0;
  min-height: 0;
}

.col-knowledge {
  width: 100%;
  min-width: 0;
  min-height: 0;
}

.col-latency {
  width: 100%;
  min-width: 0;
  min-height: 0;
}

.col-rag > *,
.col-token > *,
.col-memory > *,
.col-knowledge > *,
.col-latency > * {
  height: 100%;
  width: 100%;
  min-width: 0;
  min-height: 0;
}

.mk-panel :deep(.card-block) {
  box-shadow: none;
}

@media (max-width: 1200px) {
  .row-upper {
    flex-direction: column;
    height: auto;
  }

  .col-rag {
    flex: 1 1 auto;
    max-width: none;
    min-height: 180px;
    max-height: none;
  }

  .col-token {
    flex: none;
    height: 300px;
  }

  .row-lower {
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    grid-template-areas:
      'memory knowledge'
      'latency latency';
  }

  .col-memory {
    grid-area: memory;
  }

  .col-knowledge {
    grid-area: knowledge;
  }

  .col-latency {
    grid-area: latency;
  }
}

@media (max-width: 768px) {
  .mk-panel {
    flex: none;
    overflow: visible;
    padding: var(--space-8);
  }

  .row-upper,
  .row-lower {
    display: flex;
    flex-direction: column;
  }

  .col-token {
    flex: none;
    height: 320px;
  }

  .col-memory,
  .col-knowledge,
  .col-latency {
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
