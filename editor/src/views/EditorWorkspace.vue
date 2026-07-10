<!--
  Editor workspace page.

  Usage:
  Main route for the knowledge editor. It composes the top command bar, file
  tree, Vditor editing pane, Agent panel, and command palette.
-->
<script setup lang="ts">
import { computed, defineAsyncComponent, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import ActivityBar from '@/components/editor_workspace/ActivityBar.vue'
import AgentPanel from '@/components/editor_workspace/AgentPanel.vue'
import CommandPalette from '@/components/editor_workspace/CommandPalette.vue'
import EditorPane from '@/components/editor_workspace/EditorPane.vue'
import FileTreePanel from '@/components/editor_workspace/FileTreePanel.vue'
import SelectionToolbar from '@/components/editor_workspace/SelectionToolbar.vue'
import TopCommandBar from '@/components/editor_workspace/TopCommandBar.vue'
import { useWorkspaceStore } from '@/stores/workspace'
import type { KnowledgeGraphNodeEvent } from '@/components/knowledge_graph/graphTypes'

const workspaceStore = useWorkspaceStore()
const GraphPane = defineAsyncComponent(() => import('@/components/editor_workspace/GraphPane.vue'))
const DashboardView = defineAsyncComponent(() => import('@/views/DashboardView.vue'))
const SearchPage = defineAsyncComponent(() => import('@/views/SearchPage.vue'))
import SettingsView from '@/views/SettingsView.vue'

function handleAskAgent(text: string) {
  workspaceStore.pendingAgentReference = text
  workspaceStore.agentSidebarOpen = true
}

const ACTIVITY_BAR_WIDTH = 40
const DEFAULT_FILE_WIDTH = 280
const DEFAULT_AGENT_WIDTH = 340
const MIN_PANEL_WIDTH = 180
const MAX_FILE_WIDTH = 460
const COLLAPSE_THRESHOLD = 150

type ResizeTarget = 'file' | 'agent'

const workspaceGrid = ref<HTMLElement | null>(null)
const fileSidebarOpen = ref(true)
const agentSidebarOpen = ref(true)
const fileWidth = ref(DEFAULT_FILE_WIDTH)
const agentWidth = ref(DEFAULT_AGENT_WIDTH)
const activeResizeTarget = ref<ResizeTarget | null>(null)

// 双向同步: 允许子组件通过 store 打开 Agent 侧边栏
watch(() => workspaceStore.agentSidebarOpen, (val) => {
  if (val !== agentSidebarOpen.value) {
    agentSidebarOpen.value = val
  }
})
watch(agentSidebarOpen, (val) => {
  if (val !== workspaceStore.agentSidebarOpen) {
    workspaceStore.agentSidebarOpen = val
  }
})


const workspaceGridStyle = computed<Record<string, string>>(() => ({
  '--file-col-width': fileSidebarOpen.value ? `${fileWidth.value}px` : '0px',
  '--file-resizer-width': fileSidebarOpen.value ? '4px' : '0px',
  '--agent-col-width': agentSidebarOpen.value ? `${agentWidth.value}px` : '0px',
  '--agent-resizer-width': agentSidebarOpen.value ? '4px' : '0px',
  '--file-mobile-row': fileSidebarOpen.value ? '300px' : '0px',
  '--agent-mobile-row': agentSidebarOpen.value ? '360px' : '0px',
}))

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max)
}

function openFileSidebar() {
  fileSidebarOpen.value = true
  fileWidth.value = Math.max(fileWidth.value, DEFAULT_FILE_WIDTH)
}

function toggleFileSidebar() {
  if (fileSidebarOpen.value) {
    fileSidebarOpen.value = false
    return
  }
  openFileSidebar()
}

function toggleAgentSidebar() {
  if (agentSidebarOpen.value) {
    agentSidebarOpen.value = false
    return
  }
  agentSidebarOpen.value = true
  agentWidth.value = Math.max(agentWidth.value, DEFAULT_AGENT_WIDTH)
}

function toggleGraphView() {
  workspaceStore.setMainView(workspaceStore.mainView === 'graph' ? 'editor' : 'graph')
}

function openDashboard() {
  workspaceStore.setMainView(workspaceStore.mainView === 'dashboard' ? 'editor' : 'dashboard')
}

function openSearch() {
  workspaceStore.setMainView(workspaceStore.mainView === 'search' ? 'editor' : 'search')
}

function openSettings() {
  workspaceStore.setMainView(workspaceStore.mainView === 'settings' ? 'editor' : 'settings')
}

async function openGraphNode(node: KnowledgeGraphNodeEvent) {
  if (node.kind === 'root') {
    return
  }
  workspaceStore.setMainView('editor')
  await workspaceStore.selectFile({
    name: node.label,
    path: node.path,
    isDir: node.kind === 'folder',
  })
}

function handleResizeMove(event: PointerEvent) {
  const grid = workspaceGrid.value
  if (!grid || !activeResizeTarget.value) {
    return
  }
  const rect = grid.getBoundingClientRect()
  if (activeResizeTarget.value === 'file') {
    const nextWidth = event.clientX - rect.left - ACTIVITY_BAR_WIDTH
    if (nextWidth < COLLAPSE_THRESHOLD) {
      fileSidebarOpen.value = false
      return
    }
    fileSidebarOpen.value = true
    fileWidth.value = clamp(nextWidth, MIN_PANEL_WIDTH, MAX_FILE_WIDTH)
    return
  }

  const nextWidth = rect.right - event.clientX
  if (nextWidth < COLLAPSE_THRESHOLD) {
    agentSidebarOpen.value = false
    return
  }
  agentSidebarOpen.value = true
  const fileColumnWidth = fileSidebarOpen.value ? fileWidth.value : 0
  const maxAgentWidth = Math.max(MIN_PANEL_WIDTH, rect.width - ACTIVITY_BAR_WIDTH - fileColumnWidth - 8)
  agentWidth.value = clamp(nextWidth, MIN_PANEL_WIDTH, maxAgentWidth)
}

function stopResize() {
  activeResizeTarget.value = null
  window.removeEventListener('pointermove', handleResizeMove)
  window.removeEventListener('pointerup', stopResize)
}

function startResize(target: ResizeTarget, event: PointerEvent) {
  event.preventDefault()
  activeResizeTarget.value = target
  window.addEventListener('pointermove', handleResizeMove)
  window.addEventListener('pointerup', stopResize)
}

function handleKeydown(event: KeyboardEvent) {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
    event.preventDefault()
    workspaceStore.openCommandPalette()
  }
  if ((event.ctrlKey || event.metaKey) && event.shiftKey && event.key.toLowerCase() === 'f') {
    event.preventDefault()
    workspaceStore.openSearch()
  }
  if (event.key === 'Escape') {
    if (workspaceStore.commandPaletteOpen) {
      workspaceStore.closeCommandPalette()
      return
    }
    workspaceStore.closeSearch()
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeydown)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleKeydown)
  stopResize()
})
</script>

<template>
  <div class="workspace-page" :class="{ resizing: activeResizeTarget }">
    <TopCommandBar @toggle-agent="toggleAgentSidebar" @toggle-graph="toggleGraphView" @open-settings="openSettings" />
    <div
      ref="workspaceGrid"
      class="workspace-grid"
      :class="{
        'file-sidebar-collapsed': !fileSidebarOpen,
        'agent-sidebar-collapsed': !agentSidebarOpen,
      }"
      :style="workspaceGridStyle"
    >
      <ActivityBar
        class="activity-col"
        :file-open="fileSidebarOpen"
        :agent-open="agentSidebarOpen"
        :graph-active="workspaceStore.mainView === 'graph'"
        :dashboard-active="workspaceStore.mainView === 'dashboard'"
        :search-active="workspaceStore.mainView === 'search'"
        :settings-active="workspaceStore.mainView === 'settings'"
        @toggle-file="toggleFileSidebar"
        @toggle-agent="toggleAgentSidebar"
        @toggle-graph="toggleGraphView"
        @open-dashboard="openDashboard"
        @open-search="openSearch"
        @open-settings="openSettings"
      />
      <FileTreePanel class="file-col ide-panel" :aria-hidden="!fileSidebarOpen" />
      <div
        class="resize-handle file-resizer"
        role="separator"
        aria-label="Resize file tree"
        @pointerdown="startResize('file', $event)"
      ></div>
      <EditorPane v-if="workspaceStore.mainView === 'editor'" class="editor-col ide-panel" />
      <GraphPane v-else-if="workspaceStore.mainView === 'graph'" class="editor-col ide-panel" @open-node="openGraphNode" />
      <DashboardView v-else-if="workspaceStore.mainView === 'dashboard'" class="editor-col ide-panel" />
      <SearchPage v-else-if="workspaceStore.mainView === 'search'" class="editor-col ide-panel" />
      <SettingsView v-else-if="workspaceStore.mainView === 'settings'" class="editor-col ide-panel" />
      <div
        class="resize-handle agent-resizer"
        role="separator"
        aria-label="Resize Agent panel"
        @pointerdown="startResize('agent', $event)"
      ></div>
      <AgentPanel class="agent-col" :aria-hidden="!agentSidebarOpen" />
    </div>
    <CommandPalette />
    <SelectionToolbar @ask="handleAskAgent" />
  </div>
</template>

<style scoped>
.workspace-page {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  width: 100%;
  height: 100%;
  background: var(--color-canvas-soft);
}

.workspace-grid {
  display: grid;
  grid-template-columns:
    40px var(--file-col-width) var(--file-resizer-width) minmax(0, 1fr)
    var(--agent-resizer-width) var(--agent-col-width);
  column-gap: 0;
  min-width: 0;
  min-height: 0;
  padding: 0;
  transition:
    grid-template-columns 180ms ease,
    grid-template-rows 180ms ease;
}

.activity-col {
  grid-column: 1;
  min-width: 0;
  min-height: 0;
}

.file-col,
.editor-col,
.agent-col {
  min-width: 0;
  min-height: 0;
}

.file-col {
  grid-column: 2;
  overflow: hidden;
  transition:
    opacity 160ms ease,
    transform 180ms ease;
}

.file-resizer {
  grid-column: 3;
}

.editor-col {
  grid-column: 4;
}

.agent-resizer {
  grid-column: 5;
}

.agent-col {
  grid-column: 6;
  overflow: hidden;
  transition:
    opacity 160ms ease,
    transform 180ms ease;
}

.workspace-grid.file-sidebar-collapsed .file-col {
  pointer-events: none;
  opacity: 0;
  transform: translateX(-18px);
}

.workspace-grid.agent-sidebar-collapsed .agent-col {
  pointer-events: none;
  opacity: 0;
  transform: translateX(18px);
}

.workspace-grid.file-sidebar-collapsed .file-resizer,
.workspace-grid.agent-sidebar-collapsed .agent-resizer {
  pointer-events: none;
  opacity: 0;
}

.ide-panel {
  border-top: 0;
  border-bottom: 0;
  border-radius: 0;
}

.file-col {
  border-left: 0;
}

.editor-col {
  border-left: 0;
}

.resize-handle {
  min-width: 0;
  border-left: 1px solid transparent;
  border-right: 1px solid transparent;
  cursor: col-resize;
  background: transparent;
  transition:
    background var(--transition-fast),
    opacity 160ms ease;
}

.resize-handle:hover,
.workspace-page.resizing .resize-handle {
  background: var(--color-primary-soft);
}

.workspace-page.resizing {
  user-select: none;
}

.workspace-page.resizing .workspace-grid,
.workspace-page.resizing .file-col,
.workspace-page.resizing .agent-col {
  transition: none;
}

@media (max-width: 1180px) {
  .workspace-grid {
    padding-right: 0;
  }
}

@media (max-width: 760px) {
  .workspace-page {
    overflow: auto;
  }

  .workspace-grid {
    grid-template-columns: 40px minmax(0, 1fr);
    grid-template-rows: var(--file-mobile-row) minmax(520px, 70vh) var(--agent-mobile-row);
    min-height: auto;
    gap: 0;
    padding: 0;
  }

  .activity-col {
    grid-column: 1;
    grid-row: 1 / -1;
  }

  .file-col {
    grid-column: 2;
    grid-row: 1;
  }

  .editor-col {
    grid-column: 2;
    grid-row: 2;
  }

  .agent-col {
    grid-column: 2;
    grid-row: 3;
    margin: var(--space-12);
  }

  .resize-handle {
    display: none;
  }

  .file-col,
  .editor-col {
    border-right: 0;
    border-bottom: 1px solid var(--color-border);
  }
}
</style>
