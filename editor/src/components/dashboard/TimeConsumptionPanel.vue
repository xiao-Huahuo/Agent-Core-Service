<!--
  TimeConsumptionPanel —— RAG 指标、Token 消耗与耗时观测页。
-->

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import VChart from 'vue-echarts'
import 'echarts'

import { listLibraryItems } from '@/api/library'
import RagMetricsCard from '@/components/dashboard/RagMetricsCard.vue'
import TokenUsageCard from '@/components/dashboard/TokenUsageCard.vue'
import LatencyCard from '@/components/dashboard/LatencyCard.vue'
import ActivityHeatmapCard from '@/components/dashboard/ActivityHeatmapCard.vue'
import { useChatStore } from '@/stores/chat'
import { useSessionStore } from '@/stores/session'
import { useSettingsStore } from '@/stores/settings'
import { useWorkspaceStore } from '@/stores/workspace'
import type { KnowledgeFileNode } from '@/types/knowledge'

const settingsStore = useSettingsStore()
const workspaceStore = useWorkspaceStore()
const sessionStore = useSessionStore()
const chatStore = useChatStore()
const libraryBookCount = ref(0)

const userId = computed(() => settingsStore.profile.userId)
const knowledgeFiles = computed(() => workspaceStore.flatNodes.filter((node) => !node.isDir))
const knowledgeFileCount = computed(() => knowledgeFiles.value.length)
const latestAgentSession = computed(() => {
  return [...sessionStore.sessions]
    .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
    [0] ?? null
})
const activeSessionLastMessage = computed(() => {
  if (latestAgentSession.value?.session_id !== sessionStore.currentSessionId) return ''
  for (let index = chatStore.messages.length - 1; index >= 0; index -= 1) {
    const message = chatStore.messages[index]
    if (message?.role === 'assistant' && message.content.trim()) return message.content.trim()
  }
  return ''
})

const fileTypeSlices = computed(() => {
  const counts = new Map<string, number>()
  for (const node of knowledgeFiles.value) {
    const type = fileTypeOf(node)
    counts.set(type, (counts.get(type) ?? 0) + 1)
  }
  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([label, value], index) => ({ label, value, color: pieColors[index % pieColors.length] }))
})

const typePieOption = computed(() => ({
  backgroundColor: 'transparent',
  color: pieColors,
  tooltip: {
    trigger: 'item',
    formatter: '{b}: {c} 个 ({d}%)',
    backgroundColor: 'rgba(30,30,40,0.92)',
    borderColor: 'rgba(255,255,255,0.08)',
    borderWidth: 1,
    textStyle: { color: '#e5e7eb', fontSize: 12 },
  },
  legend: {
    show: false,
  },
  series: [
    {
      name: '文件类型',
      type: 'pie',
      radius: ['38%', '68%'],
      center: ['50%', '52%'],
      avoidLabelOverlap: true,
      itemStyle: {
        borderRadius: 10,
        borderColor: 'transparent',
        borderWidth: 0,
      },
      label: {
        show: true,
        formatter: '{b}\n{c}',
        color: '#5f6673',
        fontSize: 10,
        fontWeight: 'bold',
        lineHeight: 14,
      },
      emphasis: {
        label: {
          show: true,
          fontSize: 12,
          fontWeight: 'bold',
          color: '#5f6673',
          formatter: '{b}\n{c}',
        },
      },
      labelLine: {
        show: true,
        length: 9,
        length2: 6,
        smooth: 0.2,
        lineStyle: {
          color: 'rgba(120,128,140,0.45)',
          width: 1,
        },
      },
      data: fileTypeSlices.value.length > 0
        ? fileTypeSlices.value.map((item) => ({ name: item.label, value: item.value }))
        : [{ name: '暂无文件', value: 0 }],
      animationType: 'scale',
      animationEasing: 'elasticOut',
      animationDelay: (index: number) => index * 80,
    },
  ],
}))

const pieColors = [
  '#4224eb',
  '#eb2463',
  '#26a269',
  '#e2a72e',
  '#f05d5e',
]

watch(userId, () => {
  void loadLibraryBookCount()
}, { immediate: true })

onMounted(() => {
  if (workspaceStore.flatNodes.length === 0) {
    void workspaceStore.loadKnowledgeTree()
  }
})

async function loadLibraryBookCount() {
  if (!userId.value) {
    libraryBookCount.value = 0
    return
  }
  const activeUserId = userId.value
  const queue = ['']
  let count = 0
  try {
    while (queue.length > 0) {
      const parentId = queue.shift() ?? ''
      const response = await listLibraryItems({ userId: activeUserId, parentId })
      for (const item of response.items) {
        if (item.item_type === 'book') count += 1
        if (item.item_type === 'collection') queue.push(item.item_id)
      }
    }
    if (userId.value === activeUserId) {
      libraryBookCount.value = count
    }
  } catch {
    libraryBookCount.value = 0
  }
}

function openAgentSession(sessionId: string) {
  if (!userId.value) return
  sessionStore.select(sessionId)
  workspaceStore.setMainView('agent')
}

function fileTypeOf(node: KnowledgeFileNode): string {
  const name = node.name || node.path
  const dotIndex = name.lastIndexOf('.')
  if (dotIndex <= 0 || dotIndex === name.length - 1) return '无后缀'
  return name.slice(dotIndex + 1).toLowerCase()
}

function sessionTitle(session: { session_name: string; session_id: string }): string {
  return session.session_name || session.session_id
}

function formatSessionTime(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return `${date.getMonth() + 1}/${date.getDate()} ${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`
}
</script>

<template>
  <div class="time-panel">
    <div class="row-upper">
      <div class="col-rag">
        <RagMetricsCard />
      </div>
      <div class="col-token">
        <TokenUsageCard />
      </div>
    </div>

    <div class="row-lower">
      <div class="col-planning">
        <div class="planning-left">
          <div class="planning-metrics">
            <div class="metric-row">
              <span class="metric-label">知识库文件</span>
              <span class="metric-value">{{ knowledgeFileCount }}</span>
            </div>
            <div class="metric-row">
              <span class="metric-label">图书馆图书</span>
              <span class="metric-value">{{ libraryBookCount }}</span>
            </div>
          </div>

          <div class="agent-session-list">
            <div
              v-if="latestAgentSession"
              class="agent-session-detail"
              role="button"
              tabindex="0"
              title="打开 Agent 会话"
              @click="openAgentSession(latestAgentSession.session_id)"
              @keydown.enter.prevent="openAgentSession(latestAgentSession.session_id)"
              @keydown.space.prevent="openAgentSession(latestAgentSession.session_id)"
            >
              <div class="session-detail-head">
                <span class="session-title">{{ sessionTitle(latestAgentSession) }}</span>
                <span class="session-time">{{ formatSessionTime(latestAgentSession.updated_at) }}</span>
              </div>
              <div class="session-detail-grid">
                <span>Session</span>
                <strong>{{ latestAgentSession.session_id }}</strong>
                <span>创建</span>
                <strong>{{ formatSessionTime(latestAgentSession.created_at) }}</strong>
                <span>更新</span>
                <strong>{{ formatSessionTime(latestAgentSession.updated_at) }}</strong>
              </div>
              <div v-if="activeSessionLastMessage" class="agent-preview">{{ activeSessionLastMessage }}</div>
            </div>
            <div v-else class="agent-empty">暂无 Agent 对话</div>
          </div>

          <div class="type-share-panel">
            <VChart class="type-pie-chart" :option="typePieOption" autoresize />
          </div>
        </div>
        <div class="planning-right">
          <div class="planning-right-main">
            <ActivityHeatmapCard />
          </div>
        </div>
      </div>
      <div class="col-latency">
        <LatencyCard />
      </div>
    </div>
  </div>
</template>

<style scoped>
.time-panel {
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
  grid-template-columns: minmax(0, 2fr) minmax(0, 1fr);
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

.col-token {
  width: 100%;
  flex: 1;
  min-width: 0;
  min-height: 0;
}

.col-planning,
.col-latency {
  width: 100%;
  min-width: 0;
  min-height: 0;
}

.col-planning {
  display: grid;
  grid-template-columns: minmax(280px, 0.8fr) minmax(0, 2.4fr);
  gap: var(--space-10);
}

.planning-left {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-surface-raised);
}

.planning-right-main {
  display: flex;
  width: 100%;
  flex: 1 1 auto;
  align-items: flex-end;
  min-width: 0;
  min-height: 0;
}

.planning-right-main > * {
  width: 100%;
  height: auto;
  min-width: 0;
  min-height: 0;
}

.planning-left {
  display: flex;
  flex-direction: column;
  gap: var(--space-10);
  min-width: 0;
  min-height: 0;
  overflow: auto;
  padding: var(--space-10);
}

.planning-metrics {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--space-8);
}

.metric-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-8);
  min-height: 58px;
  min-width: 0;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  padding: var(--space-10) var(--space-12);
  background: rgba(255, 255, 255, 0.02);
}

.metric-label {
  min-width: 0;
  overflow: hidden;
  color: var(--color-text-tertiary);
  font-family: var(--font-ui);
  font-size: var(--font-size-xs);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.metric-value {
  flex: 0 0 auto;
  color: var(--color-primary);
  font-family: var(--font-ui);
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
}

.agent-session-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-8);
  min-height: 0;
}

.agent-session-detail {
  border: 1px solid var(--color-border);
  border-radius: 6px;
  padding: var(--space-8);
  background: color-mix(in srgb, var(--color-surface) 72%, transparent);
  color: var(--color-text-secondary);
  cursor: pointer;
  font-family: var(--font-ui);
  outline: none;
  transition:
    border-color var(--transition-fast),
    background var(--transition-fast),
    opacity var(--transition-fast);
}

.agent-session-detail:hover,
.agent-session-detail:focus-visible {
  border-color: var(--color-primary);
  background: var(--color-primary-softer);
}

.session-detail-head {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  align-items: center;
  gap: 3px;
  margin-bottom: var(--space-8);
}

.session-title,
.agent-preview {
  min-width: 0;
  overflow-wrap: anywhere;
  white-space: normal;
}

.session-title {
  color: var(--color-text-primary);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
}

.session-time {
  color: var(--color-text-tertiary);
  font-size: calc(10px * var(--font-scale));
  white-space: nowrap;
}

.session-detail-grid {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 5px var(--space-8);
  margin-bottom: var(--space-8);
  color: var(--color-text-tertiary);
  font-size: calc(10px * var(--font-scale));
}

.session-detail-grid strong {
  min-width: 0;
  color: var(--color-text-secondary);
  font-weight: var(--font-weight-medium);
  overflow-wrap: anywhere;
  white-space: normal;
}

.agent-preview,
.agent-empty {
  min-height: 32px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  padding: 7px var(--space-8);
  color: var(--color-text-tertiary);
  font-family: var(--font-ui);
  font-size: calc(11px * var(--font-scale));
  background: transparent;
}

.type-share-panel {
  display: flex;
  width: 100%;
  aspect-ratio: 1;
  min-height: 0;
  margin-top: auto;
  background: transparent;
}

.type-pie-chart {
  flex: 1;
  width: 100%;
  min-width: 0;
  min-height: 0;
}

.planning-right {
  display: flex;
  min-width: 0;
  min-height: 0;
}

.col-rag > *,
.col-token > *,
.col-latency > * {
  height: 100%;
  width: 100%;
  min-width: 0;
  min-height: 0;
}

.time-panel :deep(.card-block) {
  box-shadow: none;
}

@media (max-width: 1200px) {
  .row-lower {
    grid-template-columns: minmax(0, 1fr);
  }

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

  .col-planning {
    grid-template-columns: minmax(180px, 0.65fr) minmax(0, 1.35fr);
  }
}

@media (max-width: 768px) {
  .time-panel {
    flex: none;
    overflow: visible;
    padding: var(--space-8);
  }

  .row-upper,
  .row-lower {
    display: flex;
    flex-direction: column;
  }

  .col-planning {
    display: flex;
    flex-direction: column;
  }

  .planning-right {
    min-height: 420px;
  }

  .col-token {
    flex: none;
    height: 320px;
  }

  .col-latency {
    flex: none;
    height: 320px;
  }
}

@media (max-width: 560px) {
  .time-panel {
    gap: var(--space-8);
    padding: var(--space-8) var(--space-6);
  }
}
</style>
