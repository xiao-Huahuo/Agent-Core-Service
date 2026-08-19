<!--
  Workspace embedded knowledge graph pane.

  Usage:
  Renders the reusable KnowledgeGraphCanvas inside the editor center column.
  This component adapts workspace store data to graph data and emits node-open
  events upward; it intentionally does not own route navigation or file opening.
-->
<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'

import IcIcon from '@/components/common/IcIcon.vue'
import { deduplicateKnowledgeGraph, fetchKnowledgeGraph, getDedupStatus, readKnowledgeFile } from '@/api/knowledge'
import { listLibraryItems, listLibraryTags } from '@/api/library'
import KnowledgeGraphCanvas from '@/components/knowledge_graph/KnowledgeGraphCanvas.vue'
import { buildFileTreeGraph } from '@/components/knowledge_graph/fileTreeGraphAdapter'
import { buildLibraryGraph } from '@/components/knowledge_graph/libraryGraphAdapter'
import { buildSemanticKnowledgeGraph } from '@/components/knowledge_graph/semanticGraphAdapter'
import { buildWikiLinkGraph } from '@/components/knowledge_graph/wikiLinkGraphAdapter'
import { flattenWikiFiles } from '@/components/editor_workspace/wikiLinks'
import { useSettingsStore } from '@/stores/settings'
import { useWorkspaceStore } from '@/stores/workspace'
import type { KnowledgeSemanticGraphResponse, LibraryItem, LibraryTag } from '@/types/knowledge'
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
const graphMode = ref<'tree' | 'semantic' | 'library' | 'wiki'>('semantic')
const graphModeRef = ref<HTMLElement | null>(null)
const graphModeSliderStyle = ref({ width: '0px', left: '0px' })

function updateGraphModeSlider() {
  nextTick(() => {
    const container = graphModeRef.value
    if (!container) return
    const active = container.querySelector('.graph-mode-button.active') as HTMLElement | null
    if (!active) return
    graphModeSliderStyle.value = {
      width: `${active.offsetWidth}px`,
      left: `${active.offsetLeft}px`,
    }
  })
}
const semanticGraph = ref<KnowledgeSemanticGraphResponse | null>(null)
const semanticLoading = ref(false)
const semanticError = ref('')
const libraryItems = ref<LibraryItem[]>([])
const libraryTags = ref<LibraryTag[]>([])
const selectedLibraryTag = ref('')
const libraryLoading = ref(false)
/** Successfully loaded Markdown sources used by the wiki-link adapter. */
const wikiLinkDocuments = ref<Record<string, string>>({})
/** Disables refresh while the complete Markdown corpus is being read. */
const wikiLinkLoading = ref(false)
const dedupLoading = ref(false)
const dedupProgress = ref(0) // 0~100
const dedupMessage = ref('')
let dedupTimer: ReturnType<typeof setInterval> | null = null

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

const filteredLibraryItems = computed(() => {
  if (!selectedLibraryTag.value) return libraryItems.value
  const allowedCollectionIds = new Set<string>()
  const allowedItemIds = new Set(
    libraryItems.value
      .filter((item) => item.tags.includes(selectedLibraryTag.value))
      .map((item) => item.item_id),
  )
  const includeDescendants = (parentId: string) => {
    for (const child of libraryItems.value.filter((item) => item.parent_id === parentId)) {
      allowedItemIds.add(child.item_id)
      if (child.item_type === 'collection') {
        includeDescendants(child.item_id)
      }
    }
  }
  for (const itemId of [...allowedItemIds]) {
    const item = libraryItems.value.find((candidate) => candidate.item_id === itemId)
    if (item?.item_type === 'collection') {
      includeDescendants(item.item_id)
    }
  }
  for (const item of libraryItems.value) {
    if (!allowedItemIds.has(item.item_id)) continue
    let parentId = item.parent_id
    while (parentId) {
      allowedCollectionIds.add(parentId)
      parentId = libraryItems.value.find((candidate) => candidate.item_id === parentId)?.parent_id ?? ''
    }
  }
  return libraryItems.value.filter((item) => allowedItemIds.has(item.item_id) || allowedCollectionIds.has(item.item_id))
})

const graphModel = computed(() => {
  if (graphMode.value === 'semantic') {
    return buildSemanticKnowledgeGraph(semanticGraph.value, knowledgeTitle.value)
  }
  if (graphMode.value === 'library') {
    return buildLibraryGraph(filteredLibraryItems.value, { rootLabel: knowledgeTitle.value })
  }
  if (graphMode.value === 'wiki') {
    return buildWikiLinkGraph(tree.value, wikiLinkDocuments.value)
  }
  return buildFileTreeGraph(tree.value, { rootLabel: knowledgeTitle.value })
})

const graphStats = computed(() => {
  const links = graphModel.value.links
  return {
    nodes: graphModel.value.nodes.length,
    links: links.length,
    references: links.filter((link) => link.kind === 'reference').reduce((sum, link) => sum + (link.weight ?? 1), 0),
    embeds: links.filter((link) => link.kind === 'embed').reduce((sum, link) => sum + (link.weight ?? 1), 0),
  }
})

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
  if (graphMode.value === 'wiki' && node.path) {
    emit('open-node', node)
    return
  }
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
  if (graphMode.value === 'library') {
    void loadLibraryGraph()
    return
  }
  if (graphMode.value === 'wiki') {
    void loadWikiLinkGraph()
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

async function loadLibraryGraph() {
  if (!settingsStore.profile.userId) return
  libraryLoading.value = true
  try {
    const [items, tagResponse] = await Promise.all([
      loadLibraryItemsRecursive(''),
      listLibraryTags(settingsStore.profile.userId),
    ])
    libraryItems.value = items
    libraryTags.value = tagResponse.tags
    if (selectedLibraryTag.value && !tagResponse.tags.some((tag) => tag.name === selectedLibraryTag.value)) {
      selectedLibraryTag.value = ''
    }
  } finally {
    libraryLoading.value = false
  }
}

/** Reads every Markdown source and rebuilds the complete wiki-link graph input. */
async function loadWikiLinkGraph() {
  if (!settingsStore.profile.userId) return
  wikiLinkLoading.value = true
  try {
    if (tree.value.length === 0) await workspaceStore.loadKnowledgeTree()
    const markdownFiles = flattenWikiFiles(tree.value).filter((node) => /\.(?:md|markdown)$/iu.test(node.path))
    const results = await Promise.allSettled(
      markdownFiles.map(async (node) => [
        node.path,
        (await readKnowledgeFile(settingsStore.profile.userId, node.path)).content,
      ] as const),
    )
    wikiLinkDocuments.value = Object.fromEntries(
      results.flatMap((result) => result.status === 'fulfilled' ? [result.value] : []),
    )
    const failedCount = results.filter((result) => result.status === 'rejected').length
    if (failedCount > 0) workspaceStore.showToast(`${failedCount} 个 Markdown 文件读取失败，双向链接图谱可能不完整`)
  } finally {
    wikiLinkLoading.value = false
  }
}

async function loadLibraryItemsRecursive(parentId: string): Promise<LibraryItem[]> {
  const response = await listLibraryItems({
    userId: settingsStore.profile.userId,
    parentId,
    sort: 'updated_at',
    direction: 'desc',
  })
  const descendants = await Promise.all(
    response.items
      .filter((item) => item.item_type === 'collection')
      .map((item) => loadLibraryItemsRecursive(item.item_id)),
  )
  return [...response.items, ...descendants.flat()]
}

function cycleLibraryTag() {
  const options = ['', ...libraryTags.value.map((tag) => tag.name)]
  const currentIndex = Math.max(0, options.indexOf(selectedLibraryTag.value))
  selectedLibraryTag.value = options[(currentIndex + 1) % options.length] ?? ''
}

const libraryTagTitle = computed(() => selectedLibraryTag.value ? `图书馆标签: ${selectedLibraryTag.value}` : '图书馆标签: 全部')

async function handleDedup() {
  if (!settingsStore.profile.userId) return
  dedupLoading.value = true
  dedupProgress.value = 0
  dedupMessage.value = '正在启动去重…'
  try {
    await deduplicateKnowledgeGraph(settingsStore.profile.userId)
    // 轮询进度
    await pollDedupProgress()
    // 完成后刷新图谱
    await loadSemanticGraph()
  } catch (error) {
    if (error instanceof Error && error.message.includes('already_running')) {
      dedupMessage.value = '去重已在运行中'
    } else {
      semanticError.value = error instanceof Error ? error.message : '去重失败'
    }
  } finally {
    dedupLoading.value = false
    dedupProgress.value = 0
    dedupMessage.value = ''
  }
}

async function pollDedupProgress() {
  const userId = settingsStore.profile.userId
  if (!userId) return
  return new Promise<void>((resolve) => {
    dedupTimer = setInterval(async () => {
      try {
        const status = await getDedupStatus(userId)
        if (status.total > 0) {
          dedupProgress.value = Math.round((status.current / status.total) * 100)
        }
        dedupMessage.value = status.message
        if (status.status === 'completed' || status.status === 'failed' || status.status === 'idle') {
          if (dedupTimer) {
            clearInterval(dedupTimer)
            dedupTimer = null
          }
          resolve()
        }
      } catch {
        if (dedupTimer) {
          clearInterval(dedupTimer)
          dedupTimer = null
        }
        resolve()
      }
    }, 1500)
  })
}

onUnmounted(() => {
  if (dedupTimer) {
    clearInterval(dedupTimer)
    dedupTimer = null
  }
})

function kindLabel(kind: string): string {
  if (kind === 'root') return '根'
  if (kind === 'folder') return '文件夹'
  if (kind === 'file') return '文件'
  if (kind === 'virtual-group') return '集锦'
  if (kind === 'document') return '文档'
  if (kind === 'entity') return '实体'
  return kind
}

onMounted(() => {
  updateGraphModeSlider()
  if (settingsStore.profile.userId) {
    if (tree.value.length === 0) {
      void workspaceStore.loadKnowledgeTree()
    }
    if (graphMode.value === 'semantic') {
      void loadSemanticGraph()
    } else if (graphMode.value === 'library') {
      void loadLibraryGraph()
    }
  }
})

watch(
  graphMode,
  (mode) => {
    selectedNode.value = null
    sidebarOpen.value = false
    searchQuery.value = ''
    updateGraphModeSlider()
    if (mode === 'semantic') {
      void loadSemanticGraph()
    } else if (mode === 'library') {
      void loadLibraryGraph()
    } else if (mode === 'wiki') {
      void loadWikiLinkGraph()
    } else {
      void workspaceStore.loadKnowledgeTree()
    }
  },
)
</script>

<template>
  <section class="graph-pane">
    <header class="graph-toolbar">
      <div ref="graphModeRef" class="graph-mode">
        <div class="graph-mode-slider" :style="graphModeSliderStyle"></div>
        <button
          class="graph-mode-button"
          :class="{ active: graphMode === 'semantic' }"
          type="button"
          @click="graphMode = 'semantic'"
        >
          <IcIcon name="hub" :size="17" />
          <span>语义</span>
        </button>
        <button
          class="graph-mode-button"
          :class="{ active: graphMode === 'tree' }"
          type="button"
          @click="graphMode = 'tree'"
        >
          <IcIcon name="git" :size="17" />
          <span>文件树</span>
        </button>
        <button
          class="graph-mode-button"
          :class="{ active: graphMode === 'library' }"
          type="button"
          @click="graphMode = 'library'"
        >
          <IcIcon name="book" :size="17" />
          <span>图书馆</span>
        </button>
        <button
          class="graph-mode-button"
          :class="{ active: graphMode === 'wiki' }"
          type="button"
          @click="graphMode = 'wiki'"
        >
          <IcIcon name="link" :size="17" />
          <span>双向链接</span>
        </button>
      </div>
      <div class="graph-actions">
        <span v-if="graphMode === 'wiki'" class="graph-stat mono">
          {{ graphStats.nodes }} 文档 / {{ graphStats.references }} 反向 / {{ graphStats.embeds }} 嵌入
        </span>
        <span v-else class="graph-stat mono">{{ graphStats.nodes }} nodes / {{ graphStats.links }} links</span>
        <button
          v-if="graphMode === 'library'"
          class="graph-action"
          :class="{ active: Boolean(selectedLibraryTag) }"
          type="button"
          :title="libraryTagTitle"
          @click="cycleLibraryTag"
        >
          <IcIcon name="label" :size="15" />
          <span>{{ selectedLibraryTag || '全部' }}</span>
        </button>
        <button
          class="graph-action"
          :class="{ active: showGraphLabels }"
          type="button"
          :title="showGraphLabels ? 'Hide labels until hover' : 'Show labels'"
          @click="showGraphLabels = !showGraphLabels"
        >
          <IcIcon name="text-fields" :size="15" />
          <span>{{ showGraphLabels ? '标签' : '悬停' }}</span>
        </button>
        <button class="graph-action" type="button" title="Fit view" @click="graphCanvasRef?.fitToView()">
          <IcIcon name="center-focus" :size="15" />
          <span>适应</span>
        </button>
        <button
          class="graph-action"
          :class="{ loading: treeLoading || semanticLoading || libraryLoading || wikiLinkLoading, 'refresh-btn': true }"
          type="button"
          title="Reload graph data"
          :disabled="treeLoading || semanticLoading || libraryLoading || wikiLinkLoading"
          @click="refreshGraph"
        >
          <IcIcon name="refresh" :size="15" />
          <span>刷新</span>
        </button>
        <button
          v-if="graphMode === 'semantic'"
          class="graph-action"
          :class="{ loading: dedupLoading }"
          type="button"
          title="全量去重"
          :disabled="dedupLoading || treeLoading || semanticLoading || libraryLoading || wikiLinkLoading"
          @click="handleDedup"
        >
          <IcIcon name="refresh" :size="15" />
          <span>去重</span>
        </button>
        <button class="graph-action" type="button" :title="graphCanvasRef?.frozen ? '释放' : '定格'" @click="toggleFreeze">
          <IcIcon v-if="graphCanvasRef?.frozen" name="play" :size="15" />
          <IcIcon v-else name="pause" :size="15" />
          <span>{{ graphCanvasRef?.frozen ? '释放' : '定格' }}</span>
        </button>
      </div>
    </header>

    <!-- 去重进度条 -->
    <div v-if="dedupLoading" class="dedup-progress-bar">
      <div class="dedup-progress-fill" :style="{ width: dedupProgress + '%' }"></div>
      <span class="dedup-progress-text">{{ dedupMessage || `处理中 ${dedupProgress}%` }}</span>
    </div>

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
        <IcIcon name="search" :size="14" />
      </button>

      <!-- Sidebar -->
      <aside class="graph-sidebar" :class="{ open: sidebarOpen }">
        <div class="sidebar-header">
          <span class="sidebar-title">节点搜索</span>
          <button class="sidebar-close" type="button" @click="sidebarOpen = false">
            <IcIcon name="close" :size="14" />
          </button>
        </div>

        <!-- Search input -->
        <div class="sidebar-search">
          <IcIcon name="search" :size="14" class="search-icon" />
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
  min-height: 44px;
  padding: var(--space-8) var(--space-12);
  border-bottom: 0;
  background: var(--color-canvas);
  font-size: calc(12px * var(--font-scale));
}

.graph-actions {
  display: flex;
  align-items: center;
  gap: var(--space-6);
  flex-shrink: 0;
}

.graph-stat {
  color: var(--color-text-muted);
  font-size: calc(12px * var(--font-scale));
}

.graph-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-4);
  height: 28px;
  padding: 0 var(--space-8);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  color: var(--color-text-secondary);
  font: inherit;
  font-size: calc(12px * var(--font-scale));
}

.graph-action:hover {
  border-color: var(--color-primary);
  background: var(--color-primary-softer);
  color: var(--color-text);
}
.graph-action.refresh-btn:hover :deep(svg) { transform: rotate(90deg); }
.graph-action.refresh-btn :deep(svg) { transition: transform 0.3s; }

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
  position: relative;
  display: inline-flex;
  gap: var(--space-2);
  padding: 2px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-surface);
}

.graph-mode-slider {
  position: absolute;
  top: 2px;
  height: calc(100% - 4px);
  border-radius: 999px;
  background: var(--color-primary-soft);
  transition: left 250ms ease, width 250ms ease;
  z-index: 0;
  pointer-events: none;
}

.graph-mode-button {
  position: relative;
  z-index: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-6);
  height: 28px;
  padding: 0 var(--space-8);
  border: none;
  border-radius: 999px;
  background: transparent;
  color: var(--color-text-muted);
  font: inherit;
  font-size: calc(12px * var(--font-scale));
  white-space: nowrap;
  cursor: pointer;
  outline: none;
}

.graph-mode-button:hover {
  color: var(--color-primary);
}

.graph-mode-button.active {
  color: var(--color-primary);
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
  border-left: 0;
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-8) var(--space-12);
  border-bottom: 0;
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
.connected-kind-tag.folder,
.selected-node-kind-tag.virtual-group,
.connected-kind-tag.virtual-group {
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

/* 去重进度条 */
.dedup-progress-bar {
  position: relative;
  height: 24px;
  flex-shrink: 0;
  background: var(--color-surface-raised);
  border-bottom: 1px solid var(--color-border);
  overflow: hidden;
}

.dedup-progress-fill {
  height: 100%;
  background: var(--color-primary-soft);
  transition: width 300ms ease;
}

.dedup-progress-text {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: calc(11px * var(--font-scale));
  color: var(--color-text);
  white-space: nowrap;
}
</style>
