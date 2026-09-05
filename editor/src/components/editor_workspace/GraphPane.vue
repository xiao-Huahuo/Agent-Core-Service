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
import {
  clearKnowledgeGraphDocument,
  deduplicateKnowledgeGraph,
  deleteKnowledgeGraphNode,
  fetchKnowledgeGraph,
  getDedupStatus,
  readKnowledgeFile,
} from '@/api/knowledge'
import { listLibraryItems, listLibraryTags } from '@/api/library'
import GraphDetailsSidebar from '@/components/editor_workspace/GraphDetailsSidebar.vue'
import GraphNodeContextMenu from '@/components/editor_workspace/GraphNodeContextMenu.vue'
import KnowledgeGraphCanvas from '@/components/knowledge_graph/KnowledgeGraphCanvas.vue'
import { buildFileTreeGraph } from '@/components/knowledge_graph/fileTreeGraphAdapter'
import { buildLibraryGraph } from '@/components/knowledge_graph/libraryGraphAdapter'
import { buildSemanticKnowledgeGraph } from '@/components/knowledge_graph/semanticGraphAdapter'
import { buildWikiLinkGraph } from '@/components/knowledge_graph/wikiLinkGraphAdapter'
import { flattenWikiFiles } from '@/components/editor_workspace/wikiLinks'
import { useSettingsStore } from '@/stores/settings'
import { useWorkspaceStore } from '@/stores/workspace'
import type { KnowledgeSemanticGraphResponse, LibraryItem, LibraryTag } from '@/types/knowledge'
import type { KnowledgeGraphNodeContextEvent, KnowledgeGraphNodeEvent } from '@/components/knowledge_graph/graphTypes'

const emit = defineEmits<{
  'open-node': [node: KnowledgeGraphNodeEvent]
}>()

const props = withDefaults(defineProps<{
  /** Main workspace width used to keep the graph toolbar at one or two rows. */
  availableWidth?: number
}>(), {
  availableWidth: Number.POSITIVE_INFINITY,
})

const settingsStore = useSettingsStore()
const workspaceStore = useWorkspaceStore()
const { tree, treeLoading } = storeToRefs(workspaceStore)
const graphCanvasRef = ref<InstanceType<typeof KnowledgeGraphCanvas> | null>(null)
const compactToolbar = computed(() => props.availableWidth <= 900)
const mobileToolbar = computed(() => props.availableWidth <= 640)
const compressedToolbar = computed(() => props.availableWidth <= 360)
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
let graphModeResizeObserver: ResizeObserver | null = null

// Sidebar state
const sidebarOpen = ref(false)
const searchQuery = ref('')
const contextMenuRef = ref<InstanceType<typeof GraphNodeContextMenu> | null>(null)
const contextMenu = ref<{ open: boolean; node: KnowledgeGraphNodeEvent | null }>({ open: false, node: null })
const contextMenuStyle = ref<Record<string, string>>({ left: '0px', top: '0px' })

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
    return buildSemanticKnowledgeGraph(semanticGraph.value)
  }
  if (graphMode.value === 'library') {
    return buildLibraryGraph(filteredLibraryItems.value)
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

/** Open the semantic-node menu and keep its surface inside the viewport. */
async function handleNodeContext(event: KnowledgeGraphNodeContextEvent) {
  if (graphMode.value !== 'semantic' || !['document', 'entity'].includes(event.node.kind)) return
  contextMenu.value = { open: true, node: event.node }
  contextMenuStyle.value = { left: `${event.clientX}px`, top: `${event.clientY}px` }
  await nextTick()
  const rect = contextMenuRef.value?.getBoundingClientRect()
  if (!rect) return
  contextMenuStyle.value = {
    left: `${Math.max(0, event.clientX - Math.max(0, rect.right - window.innerWidth))}px`,
    top: `${Math.max(0, event.clientY - Math.max(0, rect.bottom - window.innerHeight))}px`,
  }
}

/** Close the node menu without changing graph selection. */
function closeNodeContextMenu() {
  contextMenu.value.open = false
}

/** Reveal the existing graph details sidebar for the context node. */
function showNodeDetails() {
  const node = contextMenu.value.node
  closeNodeContextMenu()
  if (!node) return
  selectedNode.value = node
  sidebarOpen.value = true
  searchQuery.value = ''
}

/** Open a semantic document in the workspace's existing editor sidebar. */
async function openDocumentNode() {
  const node = contextMenu.value.node
  closeNodeContextMenu()
  if (!node?.path) return
  const normalizedPath = node.path.replace(/\\/g, '/')
  const fileNode = workspaceStore.flatNodes.find((candidate) => candidate.path === normalizedPath) ?? {
    name: node.label,
    path: normalizedPath,
    isDir: false,
  }
  await workspaceStore.openEditorSidebar(fileNode)
}

/** Copy the context node's visible label through the native Clipboard API. */
async function copyNodeName() {
  const node = contextMenu.value.node
  closeNodeContextMenu()
  if (!node) return
  await navigator.clipboard?.writeText(node.label)
}

/** Persist entity deletion and reload the semantic model returned by the backend. */
async function deleteEntityNode() {
  const node = contextMenu.value.node
  closeNodeContextMenu()
  if (!node || !settingsStore.profile.userId) return
  try {
    await deleteKnowledgeGraphNode(settingsStore.profile.userId, node.id)
    selectedNode.value = null
    sidebarOpen.value = false
    await loadSemanticGraph()
  } catch (error) {
    workspaceStore.showToast(error instanceof Error ? error.message : '删除图谱节点失败')
  }
}

/** Clear one document's contributed graph and retain the document itself. */
async function clearDocumentNode() {
  const node = contextMenu.value.node
  closeNodeContextMenu()
  if (!node || !settingsStore.profile.userId) return
  try {
    await clearKnowledgeGraphDocument(settingsStore.profile.userId, node.id)
    selectedNode.value = node
    await loadSemanticGraph()
  } catch (error) {
    workspaceStore.showToast(error instanceof Error ? error.message : '清空图谱节点失败')
  }
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
  document.removeEventListener('click', closeNodeContextMenu)
  graphModeResizeObserver?.disconnect()
  graphModeResizeObserver = null
  if (dedupTimer) {
    clearInterval(dedupTimer)
    dedupTimer = null
  }
})

onMounted(() => {
  document.addEventListener('click', closeNodeContextMenu)
  updateGraphModeSlider()
  graphModeResizeObserver = new ResizeObserver(updateGraphModeSlider)
  if (graphModeRef.value) graphModeResizeObserver.observe(graphModeRef.value)
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

/** Repositions the active mode slider when responsive toolbar geometry changes. */
watch([compactToolbar, compressedToolbar], updateGraphModeSlider)
</script>

<template>
  <section
    class="graph-pane"
    :class="{ 'compact-toolbar': compactToolbar, 'mobile-toolbar': mobileToolbar, 'compressed-toolbar': compressedToolbar }"
  >
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
      <span v-if="graphMode === 'wiki'" class="graph-stat mono">
        {{ graphStats.nodes }} 文档 / {{ graphStats.references }} 反向 / {{ graphStats.embeds }} 嵌入
      </span>
      <span v-else class="graph-stat mono">{{ graphStats.nodes }} nodes / {{ graphStats.links }} links</span>
      <div class="graph-actions">
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
          <IcIcon :name="graphCanvasRef?.frozen ? 'play' : 'pause'" :size="15" morph />
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
        @node-context="handleNodeContext"
      />

      <GraphNodeContextMenu
        v-if="contextMenu.open && contextMenu.node"
        ref="contextMenuRef"
        :node="contextMenu.node"
        :menu-style="contextMenuStyle"
        @details="showNodeDetails"
        @open="openDocumentNode"
        @copy-name="copyNodeName"
        @delete="deleteEntityNode"
        @clear="clearDocumentNode"
      />

      <GraphDetailsSidebar
        v-model:search-query="searchQuery"
        :open="sidebarOpen"
        :selected-node="selectedNode"
        :search-results="searchResults"
        :connected-nodes="connectedNodes"
        @toggle="sidebarOpen = !sidebarOpen"
        @close="sidebarOpen = false"
        @select-node="selectNodeById"
      />
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
  margin-left: auto;
  color: var(--color-text-muted);
  font-size: calc(12px * var(--font-scale));
  white-space: nowrap;
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
  white-space: nowrap;
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

.graph-pane.compact-toolbar .graph-toolbar {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: var(--space-4);
}

.graph-pane.compact-toolbar .graph-mode {
  grid-column: 1;
  grid-row: 1;
  align-self: flex-start;
  justify-self: start;
  width: max-content;
  max-width: 100%;
}

.graph-pane.compact-toolbar .graph-stat {
  grid-column: 2;
  grid-row: 1;
  align-self: center;
  margin-left: 0;
}

.graph-pane.compact-toolbar .graph-actions {
  grid-column: 1 / -1;
  grid-row: 2;
  width: 100%;
  min-width: 0;
  justify-content: flex-start;
}

.graph-pane.compressed-toolbar .graph-mode {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  width: 100%;
}

.graph-pane.compressed-toolbar .graph-mode-button,
.graph-pane.compressed-toolbar .graph-action {
  padding: 0;
  justify-self: center;
}

.graph-pane.compressed-toolbar .graph-mode-button {
  width: 100%;
}

.graph-pane.compressed-toolbar .graph-action {
  width: 28px;
}

.graph-pane.compressed-toolbar .graph-mode-button span,
.graph-pane.compressed-toolbar .graph-action span,
.graph-pane.compressed-toolbar .graph-stat {
  display: none;
}

.graph-pane.compressed-toolbar .graph-actions {
  justify-content: space-around;
}

.graph-pane.mobile-toolbar .graph-stat {
  display: none;
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
