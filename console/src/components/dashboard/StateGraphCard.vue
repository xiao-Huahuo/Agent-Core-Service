<!--
  StateGraphCard — 状态转移图 + 队列任务切换卡片。
  使用 Mermaid 渲染 LangGraph 图,实时高亮当前执行节点与转换边。
-->

<script setup>
import { ref, watch, onMounted, nextTick } from 'vue'
import mermaid from 'mermaid'
import { useChatStore } from '@/stores/chat'

const chatStore = useChatStore()
const activeTab = ref('graph')
const svgRef = ref(null)
const prevNode = ref('')

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

function buildGraphCode(activeNode) {
  let code = GRAPH_CODE
  if (activeNode) {
    code += `\n  classDef highlight fill:#d99178,stroke:#d99178,color:#fff,stroke-width:2px`
    code += `\n  class ${activeNode} highlight`
  }
  return code
}

async function renderGraph() {
  const node = activeTab.value === 'graph' ? chatStore.currentNode : ''
  const code = buildGraphCode(node)
  const { svg } = await mermaid.render('langgraph-svg', code)
  svgRef.value = svg

  // 边高亮: 上次节点 → 当前节点
  if (prevNode.value && node && node !== prevNode.value) {
    await nextTick()
    highlightEdge(prevNode.value, node)
  }

  if (node) prevNode.value = node
}

function highlightEdge(from, to) {
  // Mermaid 边的 ID 格式: L-{from}-{to}-0
  const edgeId = `L-${from}-${to}-0`
  const container = document.getElementById('langgraph-container')
  if (!container) return
  const edge = container.querySelector(`#${edgeId}`)
  if (edge) {
    edge.setAttribute('stroke', '#d99178')
    edge.setAttribute('stroke-width', '1.5')
  }
  // 也找箭头 marker
  const marker = container.querySelector(`#${edgeId} + defs marker, #${edgeId}`)
  if (marker) {
    marker.setAttribute('fill', '#d99178')
  }
}

watch(() => chatStore.currentNode, () => {
  renderGraph()
})

watch(activeTab, (tab) => {
  if (tab === 'graph') nextTick(renderGraph)
})

onMounted(() => {
  renderGraph()
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
      <div v-if="svgRef" id="langgraph-container" class="graph-svg" v-html="svgRef" />
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
