<!--
  ExecutionTraceCard —— 节点执行轨迹与工具轨迹切换卡片。
  节点视图展示当前会话的运行路径，工具视图展示输入输出摘要和执行状态。
-->

<script setup>
import { ref } from 'vue'
import { useObsData } from '@/composable/useObsData'

const activeTab = ref('node')
const obs = useObsData()

function nodeAccent(tier, isCurrent) {
  if (isCurrent) return 'var(--color-accent)'
  if (tier === 'large') return 'var(--color-accent)'
  if (tier === 'small') return 'var(--color-blue)'
  return 'var(--color-text-tertiary)'
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
      <div class="titlebar-tabs">
        <button
          class="titlebar-tab"
          :class="{ active: activeTab === 'node' }"
          @click="activeTab = 'node'"
        >
          节点执行
        </button>
        <button
          class="titlebar-tab"
          :class="{ active: activeTab === 'tool' }"
          @click="activeTab = 'tool'"
        >
          工具轨迹
        </button>
      </div>
      <span class="window-status">{{ activeTab === 'node' ? obs.currentMessageRuntimePath.value.length + ' nodes' : obs.currentMessageToolRuns.value.length + ' tools' }}</span>
    </div>

    <div v-if="activeTab === 'node'" class="card-scroll">
      <div class="path-strip" v-if="obs.currentMessageRuntimePath.value.length > 0">
        <span
          v-for="(node, index) in obs.currentMessageRuntimePath.value"
          :key="`${node}-${index}`"
          class="path-node"
        >
          {{ node }}
        </span>
      </div>

      <div v-if="obs.currentMessageNodeTimeline.value.length > 0" class="timeline-list">
        <div
          v-for="item in obs.currentMessageNodeTimeline.value"
          :key="item.id"
          class="timeline-item"
          :style="{ '--node-accent': nodeAccent(item.modelTier, item.isCurrent) }"
        >
          <div class="timeline-axis">
            <span class="timeline-dot"></span>
            <span v-if="item.index !== obs.currentMessageNodeTimeline.value.length" class="timeline-line"></span>
          </div>
          <div class="timeline-content">
            <div class="timeline-header">
              <span class="timeline-node">{{ item.node }}</span>
              <span class="timeline-event">{{ item.event }}</span>
              <span v-if="item.isCurrent" class="timeline-state">active</span>
            </div>
            <p class="timeline-text">{{ item.humanReadable }}</p>
            <p v-if="item.toolName" class="timeline-sub">tool: {{ item.toolName }}</p>
          </div>
        </div>
      </div>

      <div v-else class="empty-state">
        <span class="placeholder-text">$ 等待节点执行轨迹</span>
      </div>
    </div>

    <div v-else class="card-scroll">
      <div v-if="obs.currentMessageToolRuns.value.length > 0" class="tool-list">
        <div
          v-for="tool in obs.currentMessageToolRuns.value"
          :key="tool.id"
          class="tool-item"
          :class="tool.status"
        >
          <div class="tool-header">
            <span class="tool-name">{{ tool.toolName }}</span>
            <span class="tool-status">{{ tool.status }}</span>
          </div>
          <div class="tool-block">
            <span class="tool-label">input</span>
            <pre class="tool-value">{{ tool.input }}</pre>
          </div>
          <div class="tool-block">
            <span class="tool-label">output</span>
            <pre class="tool-value">{{ tool.output }}</pre>
          </div>
        </div>
      </div>

      <div v-else class="empty-state">
        <span class="placeholder-text">$ 当前还没有工具调用轨迹</span>
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

.titlebar-tab {
  font-family: var(--font-mono);
  font-size: 9px;
  color: var(--color-text-tertiary);
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  padding: 2px 8px;
  cursor: pointer;
  transition: color var(--transition-fast), border-color var(--transition-fast), background var(--transition-fast);
}

.titlebar-tab:hover {
  color: var(--color-text-secondary);
  background: var(--color-bg-hover);
}

.titlebar-tab.active {
  color: var(--color-accent);
  border-color: rgba(217, 145, 120, 0.3);
  background: var(--color-accent-muted);
}

.path-strip {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-6);
  margin-bottom: var(--space-10);
}

.path-node,
.timeline-node,
.timeline-event,
.timeline-state,
.timeline-text,
.timeline-sub,
.tool-name,
.tool-status,
.tool-label,
.tool-value,
.placeholder-text {
  font-family: var(--font-mono);
}

.path-node {
  border: 1px solid var(--color-border);
  padding: 2px 6px;
  font-size: 9px;
  color: var(--color-text-secondary);
}

.timeline-list,
.tool-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-10);
}

.timeline-item {
  display: grid;
  grid-template-columns: 18px minmax(0, 1fr);
  gap: var(--space-8);
}

.timeline-axis {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.timeline-dot {
  width: 8px;
  height: 8px;
  background: var(--node-accent);
  margin-top: 4px;
}

.timeline-line {
  flex: 1;
  width: 1px;
  margin-top: 4px;
  background: var(--color-border);
}

.timeline-content {
  border: 1px solid var(--color-border);
  padding: var(--space-8);
  background: rgba(255, 255, 255, 0.02);
}

.timeline-header {
  display: flex;
  align-items: center;
  gap: var(--space-6);
  margin-bottom: var(--space-6);
}

.timeline-node {
  font-size: 9px;
  color: var(--node-accent);
  text-transform: uppercase;
}

.timeline-event {
  font-size: 9px;
  color: var(--color-text-tertiary);
}

.timeline-state {
  margin-left: auto;
  font-size: 8px;
  color: var(--color-accent);
}

.timeline-text,
.timeline-sub {
  margin: 0;
  font-size: 10px;
  color: var(--color-text-secondary);
  line-height: var(--line-height-relaxed);
  white-space: pre-wrap;
  word-break: break-word;
}

.timeline-sub {
  margin-top: var(--space-4);
  color: var(--color-text-tertiary);
}

.tool-item {
  border: 1px solid var(--color-border);
  background: rgba(255, 255, 255, 0.02);
  padding: var(--space-8);
}

.tool-item.pending {
  border-color: rgba(217, 145, 120, 0.45);
}

.tool-header {
  display: flex;
  align-items: center;
  margin-bottom: var(--space-8);
}

.tool-name {
  font-size: 10px;
  color: var(--color-blue);
}

.tool-status {
  margin-left: auto;
  font-size: 8px;
  color: var(--color-text-tertiary);
  text-transform: uppercase;
}

.tool-block + .tool-block {
  margin-top: var(--space-8);
}

.tool-label {
  display: block;
  font-size: 8px;
  color: var(--color-text-tertiary);
  margin-bottom: var(--space-4);
  text-transform: uppercase;
}

.tool-value {
  margin: 0;
  padding: var(--space-6);
  background: rgba(0, 0, 0, 0.12);
  font-size: 10px;
  color: var(--color-text-secondary);
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 140px;
  overflow: auto;
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
</style>
