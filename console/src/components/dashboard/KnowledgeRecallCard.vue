<!--
  KnowledgeRecallCard —— 知识库真实召回卡片。
  展示后端真实返回的 ReRank 前候选与 ReRank 后结果,不再使用前端伪造切片。
-->

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  recallSnapshot: {
    type: Object,
    default: () => ({ pre_rerank: [], post_rerank: [] }),
  },
  isLoading: {
    type: Boolean,
    default: false,
  },
})

const activeTab = ref('pre')

const preItems = computed(() => props.recallSnapshot?.pre_rerank || [])
const postItems = computed(() => props.recallSnapshot?.post_rerank || [])
const currentItems = computed(() => (activeTab.value === 'pre' ? preItems.value : postItems.value))
const windowStatus = computed(() => (
  activeTab.value === 'pre' ? `${preItems.value.length} candidates` : `${postItems.value.length} selected`
))

function formatMemoryType(value) {
  const map = {
    knowledge_chunk: 'KNOWLEDGE CHUNK',
  }
  return map[value] || String(value || 'KNOWLEDGE').replace(/_/g, ' ').toUpperCase()
}

function formatChannels(channels) {
  return Array.isArray(channels) && channels.length > 0 ? channels.join(' + ') : '--'
}

function formatScore(value) {
  return typeof value === 'number' ? value.toFixed(3) : '--'
}
</script>

<template>
  <div class="macos-card card-block">
    <div class="macos-card-titlebar">
      <div class="traffic-lights">
        <span class="traffic-dot sm red"></span>
        <span class="traffic-dot sm yellow"></span>
        <span class="traffic-dot sm green"></span>
      </div>
      <span class="window-filename">知识库召回</span>
      <span class="window-status">{{ windowStatus }}</span>
    </div>

    <div class="card-body">
      <div class="chart-toolbar">
        <button class="chart-mode-btn" :class="{ active: activeTab === 'pre' }" @click="activeTab = 'pre'">ReRank 前</button>
        <button class="chart-mode-btn" :class="{ active: activeTab === 'post' }" @click="activeTab = 'post'">ReRank 后</button>
      </div>

      <div v-if="isLoading" class="empty-state">
        <span class="placeholder-text">$ 正在加载真实召回快照</span>
      </div>

      <div v-else-if="currentItems.length > 0" class="knowledge-list">
        <div
          v-for="item in currentItems"
          :key="`${activeTab}-${item.memory_id}`"
          class="knowledge-item"
        >
          <div class="knowledge-header">
            <span class="knowledge-type">{{ formatMemoryType(item.memory_type) }}</span>
            <span class="knowledge-score">
              {{ activeTab === 'pre' ? `merge ${formatScore(item.merged_score)}` : `final ${formatScore(item.final_score)}` }}
            </span>
          </div>
          <div class="knowledge-meta">
            <span class="knowledge-meta-item">channel {{ formatChannels(item.retrieval_channels) }}</span>
            <span v-if="activeTab === 'pre'" class="knowledge-meta-item">vector {{ formatScore(item.vector_score) }}</span>
            <span v-if="activeTab === 'pre'" class="knowledge-meta-item">keyword {{ formatScore(item.keyword_score) }}</span>
            <span v-if="activeTab === 'post'" class="knowledge-meta-item">rerank {{ formatScore(item.rerank_score) }}</span>
          </div>
          <div v-if="activeTab === 'pre' && item.matched_terms && item.matched_terms.length > 0" class="knowledge-meta">
            <span class="knowledge-meta-item">terms {{ item.matched_terms.join(' / ') }}</span>
          </div>
          <p class="knowledge-text">{{ item.content }}</p>
        </div>
      </div>

      <div v-else class="empty-state">
        <span class="placeholder-text">$ 当前会话还没有知识库召回结果</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.card-block {
  display: flex;
  flex-direction: column;
  height: 100%;
  box-shadow: var(--shadow-window);
}

.card-body {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-8);
  overflow: auto;
  padding: var(--space-10);
}

.knowledge-type,
.knowledge-score,
.knowledge-meta-item,
.knowledge-text,
.chart-mode-btn,
.placeholder-text {
  font-family: var(--font-mono);
}

.chart-toolbar {
  display: flex;
  gap: var(--space-6);
  flex-shrink: 0;
}

.chart-mode-btn {
  font-size: 9px;
  color: var(--color-text-tertiary);
  background: transparent;
  border: 1px solid transparent;
  padding: 2px 8px;
  cursor: pointer;
  transition: color var(--transition-fast), background var(--transition-fast), border-color var(--transition-fast);
}

.chart-mode-btn:hover {
  color: var(--color-text-secondary);
  background: var(--color-bg-hover);
}

.chart-mode-btn.active {
  color: var(--color-accent);
  border-color: rgba(217, 145, 120, 0.3);
  background: var(--color-accent-muted);
}

.knowledge-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-8);
}

.knowledge-item {
  border: 1px solid rgba(96, 182, 122, 0.35);
  background: rgba(255, 255, 255, 0.02);
  padding: var(--space-8);
}

.knowledge-header {
  display: flex;
  align-items: center;
  gap: var(--space-8);
  margin-bottom: var(--space-6);
}

.knowledge-type {
  font-size: 8px;
  color: var(--color-green);
  text-transform: uppercase;
}

.knowledge-score {
  margin-left: auto;
  font-size: 8px;
  color: var(--color-text-tertiary);
}

.knowledge-meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-8);
  margin-bottom: var(--space-6);
}

.knowledge-meta-item {
  font-size: 8px;
  color: var(--color-text-tertiary);
}

.knowledge-text {
  margin: 0;
  font-size: 10px;
  color: var(--color-text-secondary);
  line-height: var(--line-height-relaxed);
  white-space: pre-wrap;
  word-break: break-word;
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 160px;
  border: 1px dashed var(--color-border);
}

.placeholder-text {
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
  text-align: center;
}
</style>
