<!--
  Workspace embedded knowledge graph pane.

  Usage:
  Renders the reusable KnowledgeGraphCanvas inside the editor center column.
  This component adapts workspace store data to graph data and emits node-open
  events upward; it intentionally does not own route navigation or file opening.
-->
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Crosshair, RefreshCw, RotateCcw, Type, BrainCircuit, AlertCircle } from 'lucide-vue-next'
import { storeToRefs } from 'pinia'

import { fetchKnowledgeGraph, getKnowledgeGraphStatus, rebuildKnowledgeGraph } from '@/api/knowledge'
import KnowledgeGraphCanvas from '@/components/knowledge_graph/KnowledgeGraphCanvas.vue'
import { buildFileTreeGraph } from '@/components/knowledge_graph/fileTreeGraphAdapter'
import { buildSemanticKnowledgeGraph } from '@/components/knowledge_graph/semanticGraphAdapter'
import { useSettingsStore } from '@/stores/settings'
import { useWorkspaceStore } from '@/stores/workspace'
import type { KnowledgeSemanticGraphResponse } from '@/types/knowledge'
import type { GraphRebuildStatus } from '@/api/knowledge'
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

// Graph rebuild progress state
const rebuildStatus = ref<GraphRebuildStatus | null>(null)
const isRebuilding = ref(false)
const pollingTimer = ref<ReturnType<typeof setInterval> | null>(null)

function basename(path: string): string {
  return path.replace(/[\\/]+$/g, '').split(/[\\/]/).filter(Boolean).pop() ?? 'Knowledge Root'
}

const knowledgeTitle = computed(() => {
  const libraryName = settingsStore.activeKnowledgeLibrary?.name?.trim()
  return libraryName || basename(settingsStore.profile.knowledgeDir) || 'Knowledge Root'
})

const graphModel = computed(() => {
  if (graphMode.value === 'semantic') {
    return buildSemanticKnowledgeGraph(semanticGraph.value)
  }
  return buildFileTreeGraph(tree.value, { rootLabel: knowledgeTitle.value })
})

const graphStats = computed(() => ({
  nodes: graphModel.value.nodes.length,
  links: graphModel.value.links.length,
}))

const rebuildProgressPercent = computed(() => {
  const s = rebuildStatus.value
  if (!s || s.total <= 0) return 0
  return Math.round((s.current / s.total) * 100)
})

const statusMessage = computed(() => {
  const s = rebuildStatus.value
  if (!s || s.status === 'idle') return ''
  if (s.status === 'running') return s.message || `处理中 ${s.current}/${s.total}`
  if (s.status === 'completed') return s.message || '图谱重建完成'
  if (s.status === 'failed') return s.message || '图谱重建失败'
  return ''
})

async function loadSemanticGraph() {
  if (!settingsStore.profile.userId) {
    return
  }
  semanticLoading.value = true
  semanticError.value = ''
  try {
    semanticGraph.value = await fetchKnowledgeGraph(settingsStore.profile.userId)
  } catch (error) {
    semanticError.value = error instanceof Error ? error.message : '加载图谱失败'
    semanticGraph.value = null
  } finally {
    semanticLoading.value = false
  }
}

function startPolling() {
  stopPolling()
  pollingTimer.value = setInterval(async () => {
    if (!settingsStore.profile.userId) return
    try {
      const status = await getKnowledgeGraphStatus(settingsStore.profile.userId)
      rebuildStatus.value = status
      if (status.status === 'completed' || status.status === 'failed') {
        stopPolling()
        isRebuilding.value = false
        if (status.status === 'completed') {
          await loadSemanticGraph()
        }
      }
    } catch {
      stopPolling()
      isRebuilding.value = false
    }
  }, 2000)
}

function stopPolling() {
  if (pollingTimer.value !== null) {
    clearInterval(pollingTimer.value)
    pollingTimer.value = null
  }
}

async function startRebuild() {
  if (!settingsStore.profile.userId || isRebuilding.value) {
    return
  }
  isRebuilding.value = true
  rebuildStatus.value = { status: 'running', total: 1, current: 0, message: '启动中...' }
  try {
    const result = await rebuildKnowledgeGraph(settingsStore.profile.userId)
    if (result.status === 'already_running') {
      rebuildStatus.value = { status: 'running', total: 1, current: 0, message: '已有一个抽取任务在运行' }
    }
    startPolling()
  } catch (error) {
    isRebuilding.value = false
    rebuildStatus.value = {
      status: 'failed',
      total: 0,
      current: 0,
      message: error instanceof Error ? error.message : '启动失败',
    }
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

onBeforeUnmount(() => {
  stopPolling()
})

watch(
  graphMode,
  (mode) => {
    selectedNode.value = null
    if (mode === 'semantic') {
      void loadSemanticGraph()
    } else {
      void workspaceStore.loadKnowledgeTree()
    }
  },
)
</script>

<template>
  <section class="graph-pane">
    <header class="graph-toolbar">
      <div class="graph-mode">
        <button
          class="graph-mode-button"
          :class="{ active: graphMode === 'tree' }"
          type="button"
          @click="graphMode = 'tree'"
        >
          文件树
        </button>
        <button
          class="graph-mode-button"
          :class="{ active: graphMode === 'semantic' }"
          type="button"
          @click="graphMode = 'semantic'"
        >
          语义
        </button>
      </div>
      <div class="graph-actions">
        <span class="graph-stat mono">{{ graphStats.nodes }} nodes / {{ graphStats.links }} links</span>
        <button
          v-if="graphMode === 'semantic'"
          class="graph-action"
          :class="{ loading: isRebuilding }"
          type="button"
          :disabled="isRebuilding"
          :title="isRebuilding ? '重建中...' : '重建语义图谱'"
          @click="startRebuild"
        >
          <BrainCircuit :size="15" />
          <span>{{ isRebuilding ? '重建中' : '重建' }}</span>
        </button>
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

    <!-- Progress bar for semantic graph rebuild -->
    <div
      v-if="rebuildStatus && (rebuildStatus.status === 'running' || rebuildStatus.status === 'failed' || rebuildStatus.status === 'completed')"
      class="graph-rebuild-progress"
      :class="{
        failed: rebuildStatus.status === 'failed',
        completed: rebuildStatus.status === 'completed',
      }"
    >
      <div class="progress-bar-track">
        <div
          class="progress-bar-fill"
          :class="{ indeterminate: rebuildStatus.total <= 0 }"
          :style="{ width: rebuildStatus.total > 0 ? rebuildProgressPercent + '%' : undefined }"
        />
      </div>
      <div class="progress-message mono">
        <AlertCircle v-if="rebuildStatus.status === 'failed'" :size="12" class="icon-error" />
        {{ statusMessage }}
      </div>
    </div>

    <KnowledgeGraphCanvas
      ref="graphCanvasRef"
      class="embedded-graph"
      :model="graphModel"
      :selected-node-id="selectedNode?.id ?? ''"
      :show-labels="showGraphLabels"
      @node-open="handleNodeOpen"
      @node-select="handleNodeSelect"
    />

  </section>
</template>

<style scoped>
.graph-pane {
  display: flex;
  flex-direction: column;
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

.graph-action.loading {
  opacity: 0.6;
  pointer-events: none;
}

.graph-action:disabled {
  opacity: 0.5;
}

.graph-mode {
  display: inline-flex;
  gap: 4px;
  padding: 3px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-surface);
}

.graph-mode-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 24px;
  padding: 0 12px;
  border: 1px solid transparent;
  border-radius: 999px;
  background: transparent;
  color: var(--color-text-muted);
  font-size: 12px;
  white-space: nowrap;
}

.graph-mode-button:hover,
.graph-mode-button.active {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.graph-mode-button.active {
  background: var(--color-primary-soft);
}

.graph-rebuild-progress {
  display: flex;
  align-items: center;
  gap: var(--space-8);
  flex-shrink: 0;
  min-height: 26px;
  padding: 0 var(--space-10);
  border-bottom: 1px solid var(--color-border);
  background: var(--color-primary-softer);
}

.graph-rebuild-progress.failed {
  background: var(--color-danger-softer, rgba(220, 38, 38, 0.08));
}

.graph-rebuild-progress.completed {
  background: var(--color-success-softer, rgba(22, 163, 74, 0.08));
}

.progress-bar-track {
  flex: 1;
  min-width: 60px;
  max-width: 200px;
  height: 4px;
  border-radius: 2px;
  background: var(--color-border);
  overflow: hidden;
}

.progress-bar-fill {
  height: 100%;
  border-radius: 2px;
  background: var(--color-primary);
  transition: width 0.3s ease;
}

.progress-bar-fill.indeterminate {
  width: 30% !important;
  animation: progress-indeterminate 1.5s ease-in-out infinite;
}

@keyframes progress-indeterminate {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(400%); }
}

.progress-message {
  flex: 1;
  display: flex;
  align-items: center;
  gap: var(--space-4);
  color: var(--color-text-secondary);
  font-size: 10px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.icon-error {
  flex-shrink: 0;
  color: var(--color-danger, #dc2626);
}

.embedded-graph {
  flex: 1;
  min-width: 0;
  min-height: 0;
}
</style>
