<!--
  Workspace embedded knowledge graph pane.

  Usage:
  Renders the reusable KnowledgeGraphCanvas inside the editor center column.
  This component adapts workspace store data to graph data and emits node-open
  events upward; it intentionally does not own route navigation or file opening.
-->
<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { Crosshair, Pause, Play, RefreshCw, Search, Type, X } from 'lucide-vue-next'
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

// Sidebar state
const sidebarOpen = ref(false)
const searchQuery = ref('')

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

// Search: partial-match node labels (exclude root node, case-insensitive)
const searchResults = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return []
  return graphModel.value.nodes.filter(
    (n) => n.label.toLowerCase().includes(q) && n.kind !== 'root',
  )
})

// Connected nodes helper
function getConnectedNodeIds(nodeId: string): string[] {
  const ids = new Set<string>()
  for (const link of graphModel.value.links) {
    const sourceId = typeof link.source === 'string' ? link.source : link.source.id
    const targetId = typeof link.target === 'string' ? link.target : link.target.id
    if (sourceId === nodeId) ids.add(targetId)
    if (targetId === nodeId) ids.add(sourceId)
  }
  return [...ids]
}

const connectedNodes = computed(() => {
  if (!selectedNode.value?.id) return []
  const ids = getConnectedNodeIds(selectedNode.value.id)
  return graphModel.value.nodes.filter((n) => ids.includes(n.id))
})

function selectNodeById(id: string) {
  const node = graphModel.value.nodes.find((n) => n.id === id)
  if (!node) return
  handleNodeSelect({
    id: node.id,
    label: node.label,
    path: node.path,
    kind: node.kind,
  })
}

function handleNodeSelect(node: KnowledgeGraphNodeEvent) {
  // Toggle: clicking same node deselects
  if (selectedNode.value?.id === node.id) {
    selectedNode.value = null
    // Sync to canvas via prop change
    return
  }
  selectedNode.value = node
  sidebarOpen.value = true
  searchQuery.value = ''
}

function handleNodeOpen(node: KnowledgeGraphNodeEvent) {
  selectedNode.value = node
  emit('open-node', node)
}

function refreshGraph() {
  selectedNode.value = null
  if (graphMode.value === 'semantic') {
    void loadSemanticGraph()
    return
  }
  void workspaceStore.loadKnowledgeTree()
}

function toggleFreeze() {
  const canvas = graphCanvasRef.value
  if (!canvas) return
  if (canvas.frozen) {
    canvas.unfreezeSimulation()
  } else {
    canvas.freezeSimulation()
  }
}

async function loadSemanticGraph() {
  if (!settingsStore.profile.userId) return
  semanticLoading.value = true
  semanticError.value = ''
  try {
    const limit = settingsStore.profile.graphNodeLimit ?? 2000
    semanticGraph.value = await fetchKnowledgeGraph(settingsStore.profile.userId, limit)
  } catch (error) {
    semanticError.value = error instanceof Error ? error.message : '加载图谱失败'
    semanticGraph.value = null
  } finally {
    semanticLoading.value = false
  }
}

function kindLabel(kind: string): string {
  if (kind === 'root') return '根'
  if (kind === 'folder') return '文件夹'
  if (kind === 'file') return '文件'
  if (kind === 'document') return '文档'
  if (kind === 'entity') return '实体'
  return kind
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
    sidebarOpen.value = false
    searchQuery.value = ''
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
        <button
          class="graph-action"
          :class="{ loading: treeLoading || semanticLoading }"
          type="button"
          title="Reload graph data"
          :disabled="treeLoading || semanticLoading"
          @click="refreshGraph"
        >
          <RefreshCw :size="15" />
          <span>刷新</span>
        </button>
        <button class="graph-action" type="button" :title="graphCanvasRef?.frozen ? '释放' : '定格'" @click="toggleFreeze">
          <component :is="graphCanvasRef?.frozen ? Play : Pause" :size="15" />
          <span>{{ graphCanvasRef?.frozen ? '释放' : '定格' }}</span>
        </button>
      </div>
    </header>

    <div class="graph-body">
      <KnowledgeGraphCanvas
        ref="graphCanvasRef"
        class="embedded-graph"
        :model="graphModel"
        :selected-node-id="selectedNode?.id ?? ''"
        :show-labels="showGraphLabels"
        @node-open="handleNodeOpen"
        @node-select="handleNodeSelect"
      />

      <!-- Sidebar toggle tab -->
      <button
        class="sidebar-tab"
        :class="{ open: sidebarOpen }"
        type="button"
        :title="sidebarOpen ? '关闭节点面板' : '节点面板'"
        @click="sidebarOpen = !sidebarOpen"
      >
        <Search :size="14" />
      </button>

      <!-- Sidebar -->
      <aside class="graph-sidebar" :class="{ open: sidebarOpen }">
        <div class="sidebar-header">
          <span class="sidebar-title">节点搜索</span>
          <button class="sidebar-close" type="button" @click="sidebarOpen = false">
            <X :size="14" />
          </button>
        </div>

        <!-- Search input -->
        <div class="sidebar-search">
          <Search :size="14" class="search-icon" />
          <input
            v-model="searchQuery"
            class="search-input"
            type="text"
            placeholder="搜索节点名称..."
          />
        </div>

        <!-- Search results -->
        <div v-if="searchQuery && searchResults.length > 0" class="sidebar-section">
          <div class="sidebar-label">搜索结果</div>
          <div class="search-tags">
            <button
              v-for="node in searchResults"
              :key="node.id"
              class="search-tag"
              :class="{ active: node.id === selectedNode?.id }"
              type="button"
              @click="selectNodeById(node.id)"
            >
              {{ node.label }}
            </button>
          </div>
        </div>
        <div v-else-if="searchQuery && searchResults.length === 0" class="sidebar-empty">
          无匹配节点
        </div>

        <!-- Selected node info -->
        <div v-if="selectedNode" class="sidebar-section">
          <div class="sidebar-label">选中节点</div>
          <div class="selected-node-name">
            <span class="selected-node-kind-tag" :class="selectedNode.kind">{{ kindLabel(selectedNode.kind) }}</span>
            {{ selectedNode.label }}
          </div>
        </div>

        <!-- Connected nodes -->
        <div v-if="connectedNodes.length > 0" class="sidebar-section sidebar-section-grow">
          <div class="sidebar-label">关联节点 ({{ connectedNodes.length }})</div>
          <div class="connected-list">
            <button
              v-for="node in connectedNodes"
              :key="node.id"
              class="connected-item"
              :class="{ active: node.id === selectedNode?.id }"
              :title="node.path || node.label"
              type="button"
              @click="selectNodeById(node.id)"
            >
              <span class="connected-kind-tag" :class="node.kind">{{ kindLabel(node.kind) }}</span>
              <span class="connected-name">{{ node.label }}</span>
            </button>
          </div>
        </div>
      </aside>
    </div>
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
  font-size: calc(10px * var(--font-scale));
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
  font-size: calc(11px * var(--font-scale));
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
  font-size: calc(12px * var(--font-scale));
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

.embedded-graph {
  flex: 1;
  min-width: 0;
  min-height: 0;
}

.graph-body {
  position: relative;
  display: flex;
  flex: 1;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

/* Sidebar toggle pill on the right edge */
.sidebar-tab {
  position: absolute;
  top: 50%;
  right: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 36px;
  padding: 0;
  border: 1px solid var(--color-border);
  border-right: 0;
  border-radius: 8px 0 0 8px;
  background: var(--color-surface);
  color: var(--color-text-muted);
  transform: translateY(-50%);
}
.sidebar-tab:hover,
.sidebar-tab.open {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

/* Sidebar panel */
.graph-sidebar {
  display: flex;
  flex-direction: column;
  width: 0;
  min-width: 0;
  overflow: hidden;
  border-left: 0;
  background: var(--color-surface);
  transition:
    width 250ms ease,
    border-left-color 250ms ease;
}
.graph-sidebar.open {
  width: 280px;
  border-left: 1px solid var(--color-border);
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-8) var(--space-12);
  border-bottom: 1px solid var(--color-border);
}

.sidebar-title {
  font-size: calc(12px * var(--font-scale));
  font-weight: 600;
  color: var(--color-text);
}

.sidebar-close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  padding: 0;
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: var(--color-text-muted);
}
.sidebar-close:hover {
  background: var(--color-surface-raised);
  color: var(--color-text);
}

/* Search */
.sidebar-search {
  display: flex;
  align-items: center;
  gap: var(--space-6);
  margin: var(--space-8) var(--space-12);
  padding: var(--space-4) var(--space-8);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-surface-raised);
}

.search-icon {
  flex-shrink: 0;
  color: var(--color-text-muted);
}

.search-input {
  flex: 1;
  min-width: 0;
  border: 0;
  background: transparent;
  color: var(--color-text);
  font-size: calc(12px * var(--font-scale));
  outline: none;
}

.search-input::placeholder {
  color: var(--color-text-muted);
}

/* Sections */
.sidebar-section {
  padding: var(--space-4) var(--space-12);
}

.sidebar-section-grow {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.sidebar-label {
  margin-bottom: var(--space-4);
  color: var(--color-text-muted);
  font-size: calc(10px * var(--font-scale));
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.sidebar-empty {
  padding: var(--space-8) var(--space-12);
  color: var(--color-text-muted);
  font-size: calc(12px * var(--font-scale));
}

/* Search result pills */
.search-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-4);
}

.search-tag {
  display: inline-flex;
  align-items: center;
  min-height: 22px;
  padding: 0 10px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-surface-raised);
  color: var(--color-text);
  font-size: calc(11px * var(--font-scale));
  white-space: nowrap;
  max-width: 240px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.search-tag:hover {
  border-color: var(--color-primary);
}
.search-tag.active {
  border-color: var(--color-primary);
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

/* Selected node */
.selected-node-name {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-6) 0;
  font-size: calc(12px * var(--font-scale));
  color: var(--color-text);
}

.selected-node-kind-tag,
.connected-kind-tag {
  display: inline-flex;
  align-items: center;
  min-height: 18px;
  padding: 0 6px;
  border-radius: 4px;
  font-size: calc(10px * var(--font-scale));
  font-weight: 600;
  white-space: nowrap;
}

.selected-node-kind-tag.entity,
.connected-kind-tag.entity {
  border: 1px solid var(--color-accent);
  background: color-mix(in srgb, var(--color-accent) 12%, transparent);
  color: var(--color-accent);
}

.selected-node-kind-tag.document,
.connected-kind-tag.document {
  border: 1px solid var(--color-primary);
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

.selected-node-kind-tag.file,
.connected-kind-tag.file {
  border: 1px solid var(--color-border);
  background: var(--color-surface-raised);
  color: var(--color-text-muted);
}

.selected-node-kind-tag.folder,
.connected-kind-tag.folder {
  border: 1px solid var(--color-primary);
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

/* Connected nodes list */
.connected-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.connected-item {
  display: flex;
  align-items: center;
  gap: var(--space-6);
  width: 100%;
  padding: var(--space-4) var(--space-6);
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--color-text-secondary);
  font-size: calc(12px * var(--font-scale));
  text-align: left;
  cursor: pointer;
}
.connected-item:hover {
  background: var(--color-primary-softer);
  color: var(--color-text);
}
.connected-item.active {
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

.connected-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
