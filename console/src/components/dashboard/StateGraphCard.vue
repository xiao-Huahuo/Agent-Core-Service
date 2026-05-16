<!--
  StateGraphCard —— 状态转移图与任务队列切换卡片。
  图结构只在首次挂载时由 Mermaid 渲染一次，后续状态变化只更新高亮，
  避免节点切换时重复重绘整张图导致闪烁、消失或布局抖动。
-->

<script setup>
import { ref, watch, onMounted, nextTick } from 'vue'
import mermaid from 'mermaid'
import { useChatStore } from '@/stores/chat'

const chatStore = useChatStore()
const activeTab = ref('graph')
const svgRef = ref(null)
const graphContainerRef = ref(null)
const lastTransition = ref(null)
const activeNodeElements = ref([])
const activeEdgeElements = ref([])

mermaid.initialize({
  theme: 'dark',
  themeVariables: {
    primaryColor: '#1e1e1e',
    primaryTextColor: '#9ca3af',
    primaryBorderColor: '#3a3a3a',
    lineColor: '#4a4a4a',
    fontSize: '11px',
  },
  flowchart: {
    useMaxWidth: true,
    htmlLabels: true,
    curve: 'basis',
  },
})

const GRAPH_CODE = `flowchart TD
    %% 节点定义
    safety_input["safety_input"]
    compress["compress"]
    planner["planner"]
    agent["agent"]
    action["action"]
    reflection["reflection"]
    safety_output["safety_output"]

    %% 边
    safety_input -->|"通过"| compress
    safety_input -->|"拦截"| E1((END))
    compress --> planner
    planner --> agent
    agent -->|"工具调用"| action
    agent -->|"直接回复"| safety_output
    action --> reflection
    reflection -->|"继续/回答"| planner
    reflection -->|"上下文溢出"| compress
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
      <span class="window-status">{{ chatStore.currentNode || 'idle' }}</span>
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
    <div v-else class="macos-card-body card-placeholder">
      <span class="placeholder-text">
        $ 大模型池 / 小模型池 / 后台队列
      </span>
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

.graph-svg {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100%;
}

.graph-svg :deep(svg) {
  max-width: 100%;
  height: auto;
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
