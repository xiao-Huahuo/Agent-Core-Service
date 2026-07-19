<!--
  Language trace and context assembly panel.

  Usage:
  AgentTracePanel renders this component twice: once for the thinking language
  trace and once for the context assembly view.
-->

<script setup lang="ts">
import { computed, ref } from 'vue'

import ThinkingSteps from '@/components/chat/ThinkingSteps.vue'
import { useObsData, type AssemblyBlock } from '@/composable/useObsData'
import { useChatStore } from '@/stores/chat'
import { useSettingsStore } from '@/stores/settings'

const props = withDefaults(defineProps<{
  mode?: 'trace' | 'context'
}>(), {
  mode: 'trace',
})

const contextMode = ref<'raw' | 'readable'>('readable')
const obs = useObsData()
const chatStore = useChatStore()
const settingsStore = useSettingsStore()

const cardTitle = computed(() => props.mode === 'trace' ? '语言轨迹' : '上下文拼装')

const thinkingModeLabel = computed(() => {
  const mode = chatStore.activeAgentMode !== 'auto' ? chatStore.activeAgentMode : settingsStore.agentLoopMode
  const labels: Record<string, string> = {
    auto: '自动',
    simple: '简单',
    react: 'ReAct',
    plan: '规划',
  }
  return labels[mode] ?? mode
})

interface GroupedSource {
  id: string
  type: string
  label: string
  accent: string
  items: typeof obs.contextSources.value
}

const groupedSources = computed<GroupedSource[]>(() => {
  const groups: GroupedSource[] = []
  for (const source of obs.contextSources.value) {
    const lastGroup = groups.length > 0 ? groups[groups.length - 1]! : undefined
    if (!lastGroup || lastGroup.type !== source.type) {
      groups.push({
        id: `${source.type}-${groups.length}`,
        type: source.type,
        label: source.label,
        accent: source.accent,
        items: [source],
      })
      continue
    }
    lastGroup.items.push(source)
  }
  return groups
})

const contextAssemblyState = computed(() => obs.contextAssembly?.value ?? {
  blocks: [],
  stats: { blockCount: 0, lineCount: 0, memoryCount: 0, knowledgeCount: 0 },
})

const assemblyBlocks = computed<AssemblyBlock[]>(() => contextAssemblyState.value.blocks)
const assemblyStats = computed(() => contextAssemblyState.value.stats)

const rawContextJson = computed(() => {
  if ((obs.contextMirror?.value as unknown[])?.length > 0) {
    return JSON.stringify(obs.contextMirror.value, null, 2)
  }
  const assembly = contextAssemblyState.value
  if (!assembly.blocks || assembly.blocks.length === 0) return ''
  const payload = {
    stats: assembly.stats,
    blocks: assembly.blocks.map((block) => ({
      order: block.order,
      type: block.type,
      title: block.title,
      status: block.status,
      lineCount: block.lineCount,
      lines: block.lines,
    })),
  }
  return JSON.stringify(payload, null, 2)
})
</script>

<template>
  <section class="trace-card">
    <div class="panel-heading">
      <h3>{{ cardTitle }}</h3>
    </div>

    <div class="panel-surface" :class="{ 'trace-surface': props.mode === 'trace' }">
      <span v-if="props.mode === 'trace'" class="mode-pill">思考模式 {{ thinkingModeLabel }}</span>

      <div v-if="props.mode === 'trace'" class="card-scroll trace-view">
        <ThinkingSteps
          v-if="obs.currentMessageThinkingTraces.value.length > 0"
          :traces="obs.currentMessageThinkingTraces.value"
          :is-streaming="obs.isStreaming.value"
          :default-expanded="true"
        />
        <div v-else class="empty-state">
          <span class="placeholder-text">$ 等待 Agent 生成可观察的思考轨迹</span>
        </div>
      </div>

      <div v-else class="card-scroll context-view">
        <div class="context-toolbar">
          <button
            class="mode-button"
            :class="{ active: contextMode === 'readable' }"
            type="button"
            @click="contextMode = 'readable'"
          >
            可读格式
          </button>
          <button
            class="mode-button"
            :class="{ active: contextMode === 'raw' }"
            type="button"
            @click="contextMode = 'raw'"
          >
            Raw
          </button>
        </div>

        <div v-if="contextMode === 'readable'" class="source-groups">
          <div class="assembly-overview">
            <div class="metric-row">
              <span class="metric-label">拼装块</span>
              <span class="metric-value">{{ assemblyStats.blockCount }}</span>
            </div>
            <div class="metric-row">
              <span class="metric-label">总行数</span>
              <span class="metric-value">{{ assemblyStats.lineCount }}</span>
            </div>
            <div class="metric-row">
              <span class="metric-label">记忆/知识</span>
              <span class="metric-value">{{ assemblyStats.memoryCount }}/{{ assemblyStats.knowledgeCount }}</span>
            </div>
          </div>

          <div v-if="assemblyBlocks.length > 0" class="assembly-list">
            <div
              v-for="block in assemblyBlocks"
              :key="block.id"
              class="assembly-block"
              :style="{ '--source-accent': block.accent }"
            >
              <div class="assembly-header">
                <div class="assembly-meta">
                  <span class="assembly-order">#{{ block.order }}</span>
                  <span class="source-dot"></span>
                  <span class="assembly-title">{{ block.title }}</span>
                </div>
                <div class="assembly-status">
                  <span class="assembly-kind">{{ block.status }}</span>
                  <span class="assembly-count">{{ block.lineCount }} 行</span>
                </div>
              </div>

              <div class="assembly-body">
                <p
                  v-for="(line, lineIndex) in block.lines"
                  :key="`${block.id}-${lineIndex}`"
                  class="source-text"
                >
                  {{ line }}
                </p>
              </div>
            </div>
          </div>

          <div v-else-if="groupedSources.length > 0" class="fallback-groups">
            <div
              v-for="group in groupedSources"
              :key="group.id"
              class="source-group"
              :style="{ '--source-accent': group.accent }"
            >
              <div class="source-header">
                <span class="source-dot"></span>
                <span class="source-title">{{ group.label }}</span>
                <span class="source-count">{{ group.items.length }}</span>
              </div>
              <div class="source-items">
                <p
                  v-for="item in group.items"
                  :key="item.id"
                  class="source-text"
                >
                  {{ item.text }}
                </p>
              </div>
            </div>
          </div>

          <div v-else class="empty-state">
            <span class="placeholder-text">$ 当前还没有系统上下文可供拆解</span>
          </div>
        </div>

        <pre v-else class="raw-context"><code>{{ rawContextJson || '$ 当前没有系统上下文原文' }}</code></pre>
      </div>
    </div>
  </section>
</template>

<style scoped>
.trace-card {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}

.panel-heading {
  display: flex;
  align-items: center;
  gap: var(--space-8);
  min-height: 30px;
  padding: 0 2px var(--space-6);
}

.panel-heading h3 {
  margin: 0;
  color: var(--color-text-primary);
  font-family: var(--font-ui);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
}

.panel-surface {
  position: relative;
  display: flex;
  flex: 1;
  min-height: 0;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-surface);
  box-shadow: var(--shadow-window);
}

.trace-surface {
  padding-top: 30px;
}

.mode-pill {
  position: absolute;
  top: var(--space-8);
  right: var(--space-10);
  z-index: 2;
  padding: 3px 10px;
  border: 1px solid color-mix(in srgb, var(--color-primary) 32%, var(--color-border));
  border-radius: 999px;
  color: var(--color-primary);
  background: var(--color-primary-soft);
  font-family: var(--font-ui);
  font-size: var(--font-size-xs);
  line-height: 1.2;
}

.card-scroll {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: var(--space-10);
}

.trace-view {
  padding-top: 0;
}

.summary-label,
.summary-value,
.source-title,
.source-count,
.placeholder-text,
.metric-label,
.metric-value {
  font-family: var(--font-ui);
}

.source-text,
.raw-context {
  font-family: var(--font-text);
}

.context-toolbar {
  display: flex;
  gap: var(--space-6);
  margin-bottom: var(--space-10);
}

.mode-button {
  position: relative;
  z-index: 1;
  border: 1px solid transparent;
  border-radius: 999px;
  padding: 3px 10px;
  background: transparent;
  color: var(--color-text-tertiary);
  cursor: pointer;
  font-family: var(--font-ui);
  font-size: 9px;
  transition: color var(--transition-fast), border-color var(--transition-fast), background var(--transition-fast);
}

.mode-button:hover {
  color: var(--color-text-secondary);
  background: var(--color-bg-hover);
}

.mode-button.active {
  border-color: color-mix(in srgb, var(--color-primary) 32%, var(--color-border));
  color: var(--color-primary);
  background: var(--color-primary-soft);
}

.source-groups {
  display: flex;
  flex-direction: column;
  gap: var(--space-10);
}

.assembly-overview {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-8);
}

.metric-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-10);
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
  font-size: var(--font-size-xs);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.metric-value {
  flex: 0 0 auto;
  color: var(--color-primary);
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
}

.assembly-list,
.fallback-groups {
  display: flex;
  flex-direction: column;
  gap: var(--space-10);
}

.assembly-block,
.source-group {
  border: 1px solid var(--color-border);
  border-radius: 6px;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.02);
}

.assembly-header,
.source-header {
  display: flex;
  align-items: center;
  gap: var(--space-6);
  padding: var(--space-6) var(--space-8);
  border-bottom: 1px solid var(--color-border-light);
}

.assembly-header {
  justify-content: space-between;
}

.assembly-meta,
.assembly-status {
  display: flex;
  align-items: center;
  gap: var(--space-6);
  min-width: 0;
}

.source-dot {
  width: 8px;
  height: 8px;
  flex-shrink: 0;
  border-radius: 50%;
  background: var(--source-accent);
}

.source-title {
  color: var(--source-accent);
  font-size: 10px;
}

.assembly-order,
.assembly-title,
.assembly-kind,
.assembly-count {
  font-family: var(--font-ui);
}

.assembly-order {
  color: var(--color-text-tertiary);
  font-size: 9px;
}

.assembly-title {
  color: var(--source-accent);
  font-size: 10px;
}

.assembly-kind,
.assembly-count {
  color: var(--color-text-tertiary);
  font-size: 9px;
}

.source-count {
  margin-left: auto;
  color: var(--color-text-tertiary);
  font-size: 9px;
}

.source-items,
.assembly-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
  padding: var(--space-8);
}

.source-text {
  margin: 0;
  color: var(--color-text-secondary);
  font-size: 10px;
  line-height: var(--line-height-relaxed);
  white-space: pre-wrap;
  word-break: break-word;
}

.raw-context {
  min-height: 100%;
  margin: 0;
  color: var(--color-text-secondary);
  font-size: 10px;
  line-height: var(--line-height-relaxed);
  white-space: pre-wrap;
  word-break: break-word;
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 180px;
  border: 1px dashed var(--color-border);
  border-radius: 6px;
}

.placeholder-text {
  color: var(--color-text-tertiary);
  font-size: var(--font-size-xs);
  line-height: var(--line-height-relaxed);
  text-align: center;
}

.trace-view :deep(.thinking-panel),
.trace-view :deep(.thinking-steps),
.trace-view :deep(.thinking-step),
.trace-view :deep(.thinking-step-card),
.trace-view :deep(.step-card) {
  border: 0;
  border-radius: 0;
}

.trace-view :deep(.thinking-steps),
.trace-view :deep(.step-item),
.trace-view :deep(.step-detail) {
  border-color: transparent;
}

@media (max-width: 720px) {
  .assembly-overview {
    grid-template-columns: 1fr;
  }

  .assembly-header {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
