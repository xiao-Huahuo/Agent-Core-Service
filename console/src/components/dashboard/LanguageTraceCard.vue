<!--
  LanguageTraceCard —— 语言轨迹与上下文拼装切换卡片。
  左右切换展示当前会话的思考轨迹，以及真正送入模型前的上下文拼装模块。
  上下文页按拼装顺序展示系统提示、短期历史、重要事实摘要、记忆索引、知识索引与当前问题。
-->

<script setup>
import { computed, ref } from 'vue'
import ThinkingSteps from '@/components/chat/ThinkingSteps.vue'
import { useObsData } from '@/composable/useObsData'

const activeTab = ref('trace')
const contextMode = ref('raw')
const obs = useObsData()

const groupedSources = computed(() => {
  const groups = []
  for (const source of obs.contextSources.value) {
    const lastGroup = groups.at(-1)
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

/**
 * 安全读取上下文拼装派生结果。
 * 这里不能假定 composable 一定已经暴露 contextAssembly，
 * 否则切到“上下文拼装”分支时会因为读取 undefined.value 直接触发运行时异常。
 */
const contextAssemblyState = computed(() => obs.contextAssembly?.value ?? {})

const assemblyBlocks = computed(() => contextAssemblyState.value.blocks ?? [])
const assemblyStats = computed(() => {
  const stats = contextAssemblyState.value.stats
  return {
    blockCount: stats?.blockCount ?? 0,
    lineCount: stats?.lineCount ?? 0,
    memoryCount: stats?.memoryCount ?? 0,
    knowledgeCount: stats?.knowledgeCount ?? 0,
  }
})

const rawContextJson = computed(() => {
  const assembly = contextAssemblyState.value
  if (!assembly || !assembly.blocks || assembly.blocks.length === 0) return ''
  const payload = {
    stats: assembly.stats ?? {},
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
  <div class="macos-card card-block">
    <div class="macos-card-titlebar">
      <div class="traffic-lights">
        <span class="traffic-dot sm red"></span>
        <span class="traffic-dot sm yellow"></span>
        <span class="traffic-dot sm green"></span>
      </div>
      <div class="titlebar-tabs">
        <button
          type="button"
          class="titlebar-tab"
          :class="{ active: activeTab === 'trace' }"
          @click="activeTab = 'trace'"
        >
          语言轨迹
        </button>
        <button
          type="button"
          class="titlebar-tab"
          :class="{ active: activeTab === 'context' }"
          @click="activeTab = 'context'"
        >
          上下文拼装
        </button>
      </div>
      <span class="window-status">{{ activeTab === 'trace' ? 'live' : 'sources' }}</span>
    </div>

    <div v-if="activeTab === 'trace'" class="card-scroll trace-view">
      <div class="summary-strip">
        <div class="summary-chip">
          <span class="summary-label">会话</span>
          <span class="summary-value">{{ obs.sessionStats.value.currentSessionName }}</span>
        </div>
        <div class="summary-chip">
          <span class="summary-label">轨迹步数</span>
          <span class="summary-value">{{ obs.currentMessageThinkingTraces.value.length }}</span>
        </div>
      </div>
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
          @click="contextMode = 'readable'"
        >
          可读格式
        </button>
        <button
          class="mode-button"
          :class="{ active: contextMode === 'raw' }"
          @click="contextMode = 'raw'"
        >
          Raw
        </button>
      </div>

      <div v-if="contextMode === 'readable'" class="source-groups">
        <div class="assembly-overview">
          <div class="summary-chip">
            <span class="summary-label">拼装块</span>
            <span class="summary-value">{{ assemblyStats.blockCount }}</span>
          </div>
          <div class="summary-chip">
            <span class="summary-label">总行数</span>
            <span class="summary-value">{{ assemblyStats.lineCount }}</span>
          </div>
          <div class="summary-chip">
            <span class="summary-label">记忆/知识</span>
            <span class="summary-value">{{ assemblyStats.memoryCount }}/{{ assemblyStats.knowledgeCount }}</span>
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
</template>

<style scoped>
.card-block {
  display: flex;
  flex-direction: column;
  height: 100%;
  box-shadow: var(--shadow-window);
}

.card-scroll {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: var(--space-10);
}

.titlebar-tabs {
  display: flex;
  align-items: center;
  gap: 1px;
  margin-left: var(--space-8);
  flex-shrink: 0;
}

.titlebar-tab,
.mode-button {
  font-family: var(--font-mono);
  font-size: 9px;
  color: var(--color-text-tertiary);
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  padding: 2px 8px;
  cursor: pointer;
  pointer-events: auto;
  position: relative;
  z-index: 1;
  transition: color var(--transition-fast), border-color var(--transition-fast), background var(--transition-fast);
}

.titlebar-tab:hover,
.mode-button:hover {
  color: var(--color-text-secondary);
  background: var(--color-bg-hover);
}

.titlebar-tab.active,
.mode-button.active {
  color: var(--color-accent);
  border-color: rgba(217, 145, 120, 0.3);
  background: var(--color-accent-muted);
}

.summary-strip {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-8);
  margin-bottom: var(--space-10);
}

.summary-chip {
  min-width: 0;
  border: 1px solid var(--color-border);
  padding: var(--space-6) var(--space-8);
  background: rgba(255, 255, 255, 0.02);
}

.summary-label,
.summary-value,
.source-title,
.source-count,
.source-text,
.raw-context,
.placeholder-text {
  font-family: var(--font-mono);
}

.summary-label {
  display: block;
  font-size: 9px;
  color: var(--color-text-tertiary);
  margin-bottom: 2px;
}

.summary-value {
  font-size: 10px;
  color: var(--color-text-primary);
  word-break: break-word;
}

.context-toolbar {
  display: flex;
  gap: var(--space-6);
  margin-bottom: var(--space-10);
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

.assembly-list,
.fallback-groups {
  display: flex;
  flex-direction: column;
  gap: var(--space-10);
}

.assembly-block,
.source-group {
  border: 1px solid var(--color-border);
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
  background: var(--source-accent);
  flex-shrink: 0;
}

.source-title {
  font-size: 10px;
  color: var(--source-accent);
}

.assembly-order,
.assembly-title,
.assembly-kind,
.assembly-count {
  font-family: var(--font-mono);
}

.assembly-order {
  font-size: 9px;
  color: var(--color-text-tertiary);
}

.assembly-title {
  font-size: 10px;
  color: var(--source-accent);
}

.assembly-kind,
.assembly-count {
  font-size: 9px;
  color: var(--color-text-tertiary);
}

.source-count {
  margin-left: auto;
  font-size: 9px;
  color: var(--color-text-tertiary);
}

.source-items {
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
  padding: var(--space-8);
}

.assembly-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
  padding: var(--space-8);
}

.source-text {
  margin: 0;
  font-size: 10px;
  color: var(--color-text-secondary);
  line-height: var(--line-height-relaxed);
  white-space: pre-wrap;
  word-break: break-word;
}

.raw-context {
  margin: 0;
  min-height: 100%;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 10px;
  color: var(--color-text-secondary);
  line-height: var(--line-height-relaxed);
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 180px;
  border: 1px dashed var(--color-border);
}

.placeholder-text {
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
  text-align: center;
  line-height: var(--line-height-relaxed);
}

@media (max-width: 720px) {
  .assembly-overview {
    grid-template-columns: 1fr;
  }

  .assembly-header {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
