<!--
  StateGraphCard —— 状态转移图与任务队列切换卡片。
  图结构只在首次挂载时由 Mermaid 渲染一次，后续状态变化只更新高亮，
  避免节点切换时重复重绘整张图导致闪烁、消失或布局抖动。
-->

<script setup>
import { computed, ref, watch, onMounted, nextTick } from 'vue'
import mermaid from 'mermaid'
import { useChatStore } from '@/stores/chat'
import { useObsData } from '@/composable/useObsData'

const chatStore = useChatStore()
const obs = useObsData()
const activeTab = ref('graph')
const svgRef = ref(null)
const graphContainerRef = ref(null)
const lastTransition = ref(null)
const activeNodeElements = ref([])
const activeEdgeElements = ref([])

/** 队列任务追踪：按模型池分组，基于 currentNode 变化触发进出队动效 */
const LARGE_NODES = new Set(['agent'])
const SMALL_NODES = new Set(['compress', 'planner', 'observation', 'summary'])

const poolTasks = ref({
  large: [],
  small: [],
  background: [],
})

let taskSeq = 0
const MAX_TASKS_PER_POOL = 12

function taskPool(node) {
  if (LARGE_NODES.has(node)) return 'large'
  if (SMALL_NODES.has(node)) return 'small'
  return 'background'
}

function latestTimelineText() {
  const timeline = obs.currentMessageNodeTimeline.value
  if (!timeline || timeline.length === 0) return ''
  const last = timeline[timeline.length - 1]
  return last.humanReadable || last.event || ''
}

watch(() => chatStore.currentNode, (newNode, oldNode) => {
  if (oldNode && oldNode !== newNode) {
    // 旧节点出队
    const oldPool = taskPool(oldNode)
    const arr = poolTasks.value[oldPool]
    const idx = arr.findIndex(t => t.active && t.node === oldNode)
    if (idx >= 0) {
      const removed = arr.splice(idx, 1)[0]
      // 将旧任务标记为完成并短暂保留以触发 leave 动效
      removed.active = false
      arr.push(removed)
      setTimeout(() => {
        const i = poolTasks.value[oldPool].findIndex(t => t.id === removed.id)
        if (i >= 0) poolTasks.value[oldPool].splice(i, 1)
      }, 300)
    }
  }

  if (newNode) {
    // 新节点入队
    const newPool = taskPool(newNode)
    const arr = poolTasks.value[newPool]
    // 移除同一 pool 中之前的 active 任务
    const activeIdx = arr.findIndex(t => t.active)
    if (activeIdx >= 0) {
      const done = arr.splice(activeIdx, 1)[0]
      done.active = false
      arr.push(done)
      setTimeout(() => {
        const i = poolTasks.value[newPool].findIndex(t => t.id === done.id)
        if (i >= 0) poolTasks.value[newPool].splice(i, 1)
      }, 300)
    }
    arr.push({
      id: taskSeq++,
      node: newNode,
      active: true,
      humanReadable: latestTimelineText(),
    })
  }

  // 裁剪
  for (const key of ['large', 'small', 'background']) {
    const arr = poolTasks.value[key]
    while (arr.length > MAX_TASKS_PER_POOL) {
      arr.shift()
    }
  }
})

// 流式过程中持续更新当前任务的描述文本
watch(
  () => obs.currentMessageNodeTimeline.value.length,
  () => {
    const current = chatStore.currentNode
    if (!current) return
    const pool = taskPool(current)
    const arr = poolTasks.value[pool]
    const activeTask = arr.find(t => t.active)
    if (activeTask) {
      activeTask.humanReadable = latestTimelineText()
    }
  }
)

mermaid.initialize({
  theme: 'dark',
  themeVariables: {
    primaryColor: '#1e1e1e',
    primaryTextColor: '#9ca3af',
    primaryBorderColor: '#3a3a3a',
    lineColor: '#4a4a4a',
    fontSize: '11px',
    clusterBkg: 'transparent',
    clusterBorder: '#3a3a3a',
  },
  flowchart: {
    useMaxWidth: true,
    htmlLabels: true,
    curve: 'basis',
  },
})

const GRAPH_CODE = `flowchart TD
    safety_input["safety_input"]

    subgraph loop["Agent 循环"]
        planner["planner"]
        compress["compress"]
        agent["agent"]
        action["action"]
        observation["observation"]
    end

    safety_output["safety_output"]

    safety_input -->|"通过"| planner
    safety_input -->|"拦截"| E1((END))
    planner --> agent
    agent -->|"工具调用"| action
    agent -->|"直接回复"| safety_output
    action --> observation
    observation -->|"继续/回答"| planner
    observation -->|"上下文溢出"| compress
    compress --> planner
    safety_output --> E2((END))`

/**
 * 仅在没有缓存 SVG 时调用 Mermaid 渲染。
 * 图结构固定，后续状态变化只更新 DOM class。
 */
async function ensureGraphSvg() {
  if (svgRef.value) return
  const { svg } = await mermaid.render('langgraph-svg', GRAPH_CODE)
  svgRef.value = svg
}

/**
 * 统一处理 Mermaid 选择器中的节点名转义。
 *
 * @param {string} value
 * @returns {string}
 */
function escapeSelectorToken(value) {
  if (typeof window !== 'undefined' && window.CSS?.escape) {
    return window.CSS.escape(value)
  }
  return value.replace(/[^a-zA-Z0-9_-]/g, '\\$&')
}

/**
 * 移除上一次状态同步留下的节点和边高亮。
 */
function clearGraphHighlights() {
  for (const element of activeNodeElements.value) {
    element.classList.remove('graph-node-active')
  }
  for (const element of activeEdgeElements.value) {
    element.classList.remove('graph-edge-active')
  }
  activeNodeElements.value = []
  activeEdgeElements.value = []
}

/**
 * 根据当前节点和最近一次节点跳转更新高亮，不重新渲染 SVG。
 */
function syncGraphHighlights() {
  const container = graphContainerRef.value
  if (!container) return

  clearGraphHighlights()

  if (chatStore.currentNode) {
    const nodeSelector = `[id^="flowchart-${escapeSelectorToken(chatStore.currentNode)}-"]`
    const nodeElements = [...container.querySelectorAll(nodeSelector)]
    nodeElements.forEach((element) => element.classList.add('graph-node-active'))
    activeNodeElements.value = nodeElements
  }

  if (lastTransition.value?.from && lastTransition.value?.to) {
    const from = escapeSelectorToken(lastTransition.value.from)
    const to = escapeSelectorToken(lastTransition.value.to)
    const edgeSelector = `.LS-${from}.LE-${to}`
    const edgeElements = [...container.querySelectorAll(edgeSelector)]
    edgeElements.forEach((element) => element.classList.add('graph-edge-active'))
    activeEdgeElements.value = edgeElements
  }
}

watch(() => chatStore.currentNode, (currentNode, previousNode) => {
  if (previousNode && currentNode && previousNode !== currentNode) {
    lastTransition.value = { from: previousNode, to: currentNode }
  }
  if (!currentNode) {
    lastTransition.value = null
  }
  if (activeTab.value === 'graph') {
    nextTick(syncGraphHighlights)
  }
})

watch(activeTab, async (tab) => {
  if (tab !== 'graph') return
  await ensureGraphSvg()
  await nextTick()
  syncGraphHighlights()
})

onMounted(async () => {
  await ensureGraphSvg()
  await nextTick()
  syncGraphHighlights()
})

const queueStatusLabel = computed(() => {
  if (chatStore.currentNode) return 'running'
  return obs.schedulerSnapshot.value.globalState
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
          class="titlebar-tab"
          :class="{ active: activeTab === 'graph' }"
          @click="activeTab = 'graph'"
        >
          状态转移图
        </button>
        <button
          class="titlebar-tab"
          :class="{ active: activeTab === 'queue' }"
          @click="activeTab = 'queue'"
        >
          队列任务
        </button>
      </div>
      <span class="window-status">{{ chatStore.currentNode || queueStatusLabel }}</span>
    </div>

    <!-- 状态转移图 -->
    <div v-if="activeTab === 'graph'" class="graph-body">
      <div
        v-if="svgRef"
        ref="graphContainerRef"
        class="graph-svg"
        v-html="svgRef"
      />
      <span v-else class="placeholder-text">$ 等待 Agent 活动...</span>
    </div>

    <!-- 队列任务 -->
    <div v-else class="queue-body">
      <div class="queue-pools">
        <div
          v-for="pool in obs.schedulerSnapshot.value.pools"
          :key="pool.id"
          class="queue-pool"
          :class="pool.state"
        >
          <div class="queue-header">
            <span class="queue-dot" :class="pool.state"></span>
            <span class="queue-name">{{ pool.label }}</span>
            <span class="queue-state">{{ pool.state }}</span>
          </div>
          <TransitionGroup
            :name="'task-enter'"
            tag="div"
            class="task-list"
          >
            <div
              v-for="task in poolTasks[pool.id]"
              :key="task.id"
              class="task-item"
              :class="{ 'task-current': task.active }"
              :title="`[${task.node}] ${task.humanReadable || ''}`"
            >
              <span class="task-dot" :class="taskPool(task.node)"></span>
              <span class="task-label">{{ task.node.slice(0, 2) }}</span>
              <span class="task-tip">{{ task.humanReadable || task.node }}</span>
            </div>
          </TransitionGroup>
          <div v-if="!poolTasks[pool.id] || poolTasks[pool.id].length === 0" class="task-empty">
            <span v-if="pool.state === 'active'">等待任务…</span>
            <span v-else>空闲</span>
          </div>
        </div>
      </div>

      <div class="queue-meta">
        <span class="queue-meta-item">
          path={{ obs.runtimePath.value.join(' -> ') || 'idle' }}
        </span>
        <span class="queue-meta-item">
          trace={{ obs.nodeTimeline.value.length }}
        </span>
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

.graph-body {
  flex: 1;
  overflow: auto;
  padding: var(--space-8);
}

.queue-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--space-10);
  padding: var(--space-10);
  min-height: 0;
}

.queue-pools {
  display: flex;
  flex-direction: column;
  gap: var(--space-8);
  flex: 1;
  min-height: 0;
  overflow: auto;
}

.queue-pool {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--space-8);
  background: rgba(255, 255, 255, 0.02);
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.queue-pool.active {
  border-color: rgba(217, 145, 120, 0.45);
}

.queue-pool.queued {
  border-color: rgba(77, 166, 255, 0.45);
}

.queue-header {
  display: flex;
  align-items: center;
  gap: var(--space-6);
  margin-bottom: var(--space-8);
  flex-shrink: 0;
}

.queue-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-text-tertiary);
  flex-shrink: 0;
}

.queue-dot.active {
  background: var(--color-accent);
  box-shadow: 0 0 6px rgba(217, 145, 120, 0.6);
}

.queue-dot.queued {
  background: var(--color-blue);
}

.queue-name,
.queue-state,
.task-node,
.task-summary,
.queue-meta-item {
  font-family: var(--font-mono);
}

.queue-name {
  font-size: 10px;
  color: var(--color-text-primary);
}

.queue-state {
  margin-left: auto;
  font-size: 8px;
  color: var(--color-text-tertiary);
  text-transform: uppercase;
}

/* ---- 任务列表 ---- */
.task-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-6);
  flex: 1;
  min-height: 0;
  align-content: flex-start;
  position: relative;
}

/* ---- 正方形任务卡片 ---- */
.task-item {
  position: relative;
  width: 32px;
  height: 32px;
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-sm);
  background: rgba(255, 255, 255, 0.04);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  cursor: default;
  transition: border-color var(--transition-fast), background var(--transition-fast);
}

.task-item.task-current {
  border-color: rgba(217, 145, 120, 0.6);
  background: rgba(217, 145, 120, 0.12);
}

.task-item:hover {
  border-color: var(--color-accent);
  background: rgba(217, 145, 120, 0.1);
  z-index: 2;
}

/* ---- 方形内的点 ---- */
.task-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-text-tertiary);
  flex-shrink: 0;
}

.task-dot.large {
  background: var(--color-accent);
}

.task-dot.small {
  background: var(--color-blue);
}

/* ---- 方形内的标签 ---- */
.task-label {
  position: absolute;
  bottom: 2px;
  right: 3px;
  font-family: var(--font-mono);
  font-size: 7px;
  color: var(--color-text-tertiary);
  text-transform: uppercase;
  opacity: 0.5;
}

/* ---- 悬停浮出提示 ---- */
.task-tip {
  position: absolute;
  bottom: calc(100% + 6px);
  left: 50%;
  transform: translateX(-50%);
  font-family: var(--font-mono);
  font-size: 9px;
  color: var(--color-text-primary);
  background: rgba(30, 30, 30, 0.95);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: var(--space-6) var(--space-8);
  white-space: nowrap;
  max-width: 240px;
  overflow: hidden;
  text-overflow: ellipsis;
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.15s ease;
}

.task-item:hover .task-tip {
  opacity: 1;
}

.task-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-10) 0;
  font-family: var(--font-mono);
  font-size: 9px;
  color: var(--color-text-tertiary);
}

/* ---- 入队动效: 从右向左滑入 ---- */
.task-enter-enter-active {
  transition: transform 0.35s ease, opacity 0.3s ease;
}

.task-enter-leave-active {
  transition: transform 0.25s ease, opacity 0.2s ease;
  position: absolute;
}

.task-enter-enter-from {
  transform: translateX(60px);
  opacity: 0;
}

.task-enter-leave-to {
  transform: translateX(-40px);
  opacity: 0;
}

.task-enter-move {
  transition: transform 0.3s ease;
}

.queue-meta {
  margin-top: auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  border-top: 1px solid var(--color-border-light);
  padding-top: var(--space-8);
  flex-shrink: 0;
}

.queue-meta-item {
  font-size: 9px;
  color: var(--color-text-tertiary);
  word-break: break-word;
}

.graph-svg {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100%;
  overflow: hidden;
}

.graph-svg :deep(svg) {
  max-width: 100%;
  height: auto;
  display: block;
  pointer-events: none;
}

.graph-svg :deep(.graph-node-active .nodeLabel),
.graph-svg :deep(.graph-node-active .label) {
  fill: #fff;
  color: #fff;
}

.graph-svg :deep(.graph-node-active rect),
.graph-svg :deep(.graph-node-active polygon),
.graph-svg :deep(.graph-node-active circle),
.graph-svg :deep(.graph-node-active ellipse),
.graph-svg :deep(.graph-node-active path) {
  fill: #d99178;
  stroke: #d99178;
  stroke-width: 2px;
}

.graph-svg :deep(.graph-edge-active),
.graph-svg :deep(.graph-edge-active path) {
  stroke: #d99178 !important;
  stroke-width: 1.5px !important;
}

.graph-svg :deep(.graph-edge-active marker path),
.graph-svg :deep(.graph-edge-active polygon) {
  fill: #d99178 !important;
}

.graph-svg :deep(.cluster rect) {
  stroke: var(--color-border);
  stroke-dasharray: 6 3;
  rx: 10;
  ry: 10;
  fill: none !important;
}

.graph-svg :deep(.cluster-label) {
  display: none;
}

@media (min-width: 1201px) {
  .graph-body {
    padding: var(--space-6);
  }

  .graph-svg {
    align-items: flex-start;
  }

  .graph-svg :deep(svg) {
    min-width: 280px;
  }
}

@media (min-width: 1600px) and (min-aspect-ratio: 6/5) {
  .graph-body {
    padding: var(--space-4);
  }

  .graph-svg :deep(svg) {
    min-width: auto;
    max-height: calc(100dvh - 260px);
    width: auto;
  }
}

.card-placeholder {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-24) var(--space-16);
}

.placeholder-text {
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
  text-align: center;
  line-height: var(--line-height-relaxed);
}
</style>
