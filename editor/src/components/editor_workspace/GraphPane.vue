<!--
  Workspace embedded knowledge graph pane.

  Usage:
  Renders the reusable KnowledgeGraphCanvas inside the editor center column.
  This component adapts workspace store data to graph data and emits node-open
  events upward; it intentionally does not own route navigation or file opening.
-->
<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { Crosshair, RefreshCw, RotateCcw, Type } from 'lucide-vue-next'
import { storeToRefs } from 'pinia'

import { fetchKnowledgeGraph } from '@/api/knowledge'
import KnowledgeGraphCanvas from '@/components/knowledge_graph/KnowledgeGraphCanvas.vue'
import { buildFileTreeGraph } from '@/components/knowledge_graph/fileTreeGraphAdapter'
import { buildSemanticKnowledgeGraph } from '@/components/knowledge_graph/semanticGraphAdapter'
import { useSettingsStore } from '@/stores/settings'
import { useWorkspaceStore } from '@/stores/workspace'
import type { KnowledgeSemanticGraphResponse } from '@/types/knowledge'
import type { KnowledgeGraphNodeEvent } from '@/components/knowledge_graph/graphTypes'

const emit = defineEmits<{
  'open-node': [node: KnowledgeGraphNodeEvent]
}>()

const settingsStore = useSettingsStore()
const workspaceStore = useWorkspaceStore()
const { tree, treeLoading } = storeToRefs(workspaceStore)
const graphCanvasRef = ref<InstanceType<typeof KnowledgeGraphCanvas> | null>(null)
const selectedNode = ref<KnowledgeGraphNodeEvent | null>(null)
const showGraphLabels = ref(true)
const graphMode = ref<'tree' | 'semantic'>('tree')
const semanticGraph = ref<KnowledgeSemanticGraphResponse | null>(null)
const semanticLoading = ref(false)
const semanticError = ref('')

function basename(path: string): string {
  return path.replace(/[\\/]+$/g, '').split(/[\\/]/).filter(Boolean).pop() ?? 'Knowledge Root'
}

const knowledgeTitle = computed(() => {
  const libraryName = settingsStore.activeKnowledgeLibrary?.name?.trim()
  return libraryName || basename(settingsStore.profile.knowledgeDir) || 'Knowledge Root'
})

const graphModel = computed(() => {
  if (graphMode.value === 'semantic') {
    return buildSemanticKnowledgeGraph(semanticGraph.value, knowledgeTitle.value)
  }
  return buildFileTreeGraph(tree.value, { rootLabel: knowledgeTitle.value })
})

const graphStats = computed(() => ({
  nodes: graphModel.value.nodes.length,
  links: graphModel.value.links.length,
}))

async function loadSemanticGraph() {
  if (!settingsStore.profile.userId) {
    return
  }
  semanticLoading.value = true
  semanticError.value = ''
  try {
    semanticGraph.value = await fetchKnowledgeGraph(settingsStore.profile.userId)
  } catch (error) {
    semanticError.value = error instanceof Error ? error.message : 'failed to load graph'
    semanticGraph.value = null
  } finally {
    semanticLoading.value = false
  }
}

function handleNodeSelect(node: KnowledgeGraphNodeEvent) {
  selectedNode.value = node
  if (node.path) {
    emit('open-node', node)
  }
}

function handleNodeOpen(node: KnowledgeGraphNodeEvent) {
  selectedNode.value = node
  if (node.path) {
    emit('open-node', node)
  }
}

function refreshGraph() {
  selectedNode.value = null
  if (graphMode.value === 'semantic') {
    void loadSemanticGraph()
    return
  }
  void workspaceStore.loadKnowledgeTree()
}

onMounted(() => {
  if (settingsStore.profile.userId && tree.value.length === 0) {
    void workspaceStore.loadKnowledgeTree()
  }
})

watch(
  graphMode,
  (mode) => {
    selectedNode.value = null
    if (mode === 'semantic') {
      void loadSemanticGraph()
    }
  },
)
</script>

<template>
  <section class="graph-pane">
    <header class="graph-toolbar">
      <div class="graph-title">
        <span class="eyebrow mono">知识图谱</span>
        <strong>{{ knowledgeTitle }}</strong>
      </div>
      <div class="graph-actions">
        <span class="graph-stat mono">{{ graphStats.nodes }} nodes / {{ graphStats.links }} links</span>
        <button
          class="graph-action"
          :class="{ active: showGraphLabels }"
          type="button"
          :title="showGraphLabels ? 'Hide labels until hover' : 'Show labels'"
          @click="showGraphLabels = !showGraphLabels"
        >
          <Type :size="15" />
          <span>{{ showGraphLabels ? '标签' : '悬停' }}</span>
        </button>
        <button class="graph-action" type="button" title="Fit view" @click="graphCanvasRef?.fitToView()">
          <Crosshair :size="15" />
          <span>适应</span>
        </button>
        <button class="graph-action" type="button" title="Reload graph data" @click="refreshGraph">
          <RefreshCw :size="15" />
          <span>刷新</span>
        </button>
        <button class="graph-action" type="button" title="Reheat layout" @click="graphCanvasRef?.reheatLayout()">
          <RotateCcw :size="15" />
          <span>重排</span>
        </button>
      </div>
    </header>

    <KnowledgeGraphCanvas
      ref="graphCanvasRef"
      class="embedded-graph"
      :model="graphModel"
      :selected-node-id="selectedNode?.id ?? ''"
      :show-labels="showGraphLabels"
      @node-open="handleNodeOpen"
      @node-select="handleNodeSelect"
    />

    <footer class="graph-status">
      <span v-if="graphMode === 'tree' && treeLoading" class="mono">加载文件树...</span>
      <span v-else-if="graphMode === 'semantic' && semanticLoading" class="mono">加载知识图谱...</span>
      <span v-else-if="graphMode === 'semantic' && semanticError" class="mono">{{ semanticError }}</span>
      <span v-else-if="selectedNode" class="mono">{{ selectedNode.path || selectedNode.label }}</span>
      <span v-else class="mono">{{ graphMode === 'tree' ? '点击节点在编辑器中打开' : '点击节点查看关联' }}</span>
    </footer>
  </section>
</template>

<style scoped>
.graph-pane {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  background: var(--color-canvas-soft);
}

.graph-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-12);
  min-height: 38px;
  padding: 0 var(--space-10);
  border-bottom: 1px solid var(--color-border);
  background: var(--color-canvas);
}

.graph-title {
  min-width: 0;
}

.graph-title strong {
  display: block;
  overflow: hidden;
  color: var(--color-text);
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.eyebrow {
  display: block;
  color: var(--color-text-muted);
  font-size: 9px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.graph-actions {
  display: flex;
  align-items: center;
  gap: var(--space-6);
  flex-shrink: 0;
}

.graph-stat {
  color: var(--color-text-muted);
  font-size: 10px;
}

.graph-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-4);
  height: 24px;
  padding: 0 var(--space-8);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  color: var(--color-text-secondary);
  font-size: 11px;
}

.graph-action:hover {
  border-color: var(--color-primary);
  background: var(--color-primary-softer);
  color: var(--color-text);
}

.graph-action.active {
  border-color: var(--color-primary);
  background: var(--color-primary-softer);
  color: var(--color-primary);
}

.graph-mode {
  display: inline-flex;
  height: 24px;
  border: 1px solid var(--color-border);
  background: var(--color-surface);
}

.graph-mode-button {
  height: 22px;
  padding: 0 var(--space-8);
  border: 0;
  border-right: 1px solid var(--color-border);
  background: transparent;
  color: var(--color-text-muted);
  font-size: 11px;
}

.graph-mode-button:last-child {
  border-right: 0;
}

.graph-mode-button.active {
  background: var(--color-primary-softer);
  color: var(--color-primary);
}

.embedded-graph {
  min-width: 0;
  min-height: 0;
}

.graph-status {
  display: flex;
  align-items: center;
  min-height: 24px;
  padding: 0 var(--space-10);
  border-top: 1px solid var(--color-border);
  background: var(--color-canvas);
  color: var(--color-text-muted);
  font-size: 10px;
  overflow: hidden;
}

.graph-status span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
