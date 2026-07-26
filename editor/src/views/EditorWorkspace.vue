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
import ImagePreviewer from '@/components/common/ImagePreviewer.vue'
import FileConflictDialog from '@/components/editor_workspace/FileConflictDialog.vue'
import FileTreePanel from '@/components/editor_workspace/FileTreePanel.vue'
import FileResourceManager from '@/components/editor_workspace/FileResourceManager.vue'
import SelectionToolbar from '@/components/editor_workspace/SelectionToolbar.vue'
import TodoSidebar from '@/components/editor_workspace/TodoSidebar.vue'
import TopCommandBar from '@/components/editor_workspace/TopCommandBar.vue'
import { useWorkspaceStore } from '@/stores/workspace'
import type { KnowledgeGraphNodeEvent } from '@/components/knowledge_graph/graphTypes'

const workspaceStore = useWorkspaceStore()
const AgentPage = defineAsyncComponent(() => import('@/views/AgentPage.vue'))
const GraphPane = defineAsyncComponent(() => import('@/components/editor_workspace/GraphPane.vue'))
const DashboardView = defineAsyncComponent(() => import('@/views/DashboardView.vue'))
const DebugView = defineAsyncComponent(() => import('@/views/DebugView.vue'))
const IngestionProgressView = defineAsyncComponent(() => import('@/views/IngestionProgressView.vue'))
const LibraryView = defineAsyncComponent(() => import('@/views/LibraryView.vue'))
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
const isAgentPage = computed(() => workspaceStore.mainView === 'agent')
const isGraphPage = computed(() => workspaceStore.mainView === 'graph')
const sidebarHidden = computed(() => isAgentPage.value || isGraphPage.value)
const visibleFileSidebarOpen = computed(() => fileSidebarOpen.value && !sidebarHidden.value)
const visibleAgentSidebarOpen = computed(() => (agentSidebarOpen.value || todoSidebarOpen.value) && !sidebarHidden.value)
const showConflictDialog = computed(() => {
  return workspaceStore.conflictDialog.open
})

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
  '--file-col-width': visibleFileSidebarOpen.value ? `${fileWidth.value}px` : '0px',
  '--file-resizer-width': visibleFileSidebarOpen.value ? '4px' : '0px',
  '--agent-col-width': visibleAgentSidebarOpen.value ? `${agentWidth.value}px` : '0px',
  '--agent-resizer-width': visibleAgentSidebarOpen.value ? '4px' : '0px',
  '--file-mobile-row': visibleFileSidebarOpen.value ? '300px' : '0px',
  '--agent-mobile-row': visibleAgentSidebarOpen.value ? '360px' : '0px',
}))

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max)
}

function openFileSidebar() {
  if (workspaceStore.mainView === 'resources') {
    workspaceStore.setMainView('editor')
  }
  fileSidebarOpen.value = true
  fileWidth.value = Math.max(fileWidth.value, DEFAULT_FILE_WIDTH)
}

function toggleFileSidebar() {
  if (sidebarHidden.value) {
    workspaceStore.setMainView('editor')
    openFileSidebar()
    return
  }
  if (fileSidebarOpen.value) {
    fileSidebarOpen.value = false
    return
  }
  openFileSidebar()
}

function toggleAgentSidebar() {
  if (sidebarHidden.value) {
    workspaceStore.setMainView('editor')
    agentSidebarOpen.value = true
    agentWidth.value = Math.max(agentWidth.value, DEFAULT_AGENT_WIDTH)
    return
  }
  agentSidebarOpen.value = !agentSidebarOpen.value
  if (agentSidebarOpen.value) {
    agentWidth.value = Math.max(agentWidth.value, DEFAULT_AGENT_WIDTH)
  }
}

const todoSidebarOpen = ref(false)
const todoSplitRatio = ref(0.5)
const TODO_COLLAPSE_THRESHOLD = 0.12
watch(() => workspaceStore.todoSidebarOpen, (val) => {
  todoSidebarOpen.value = val
})

watch(todoSidebarOpen, (val) => {
  workspaceStore.todoSidebarOpen = val
})

function toggleTodoSidebar() {
  if (sidebarHidden.value) {
    workspaceStore.setMainView('editor')
  }
  todoSidebarOpen.value = !todoSidebarOpen.value
  if (todoSidebarOpen.value) {
    agentWidth.value = Math.max(agentWidth.value, DEFAULT_AGENT_WIDTH)
    todoSplitRatio.value = 0.5
  }
}

let activeTodoResize = false

function startTodoResize(event: PointerEvent) {
  event.preventDefault()
  activeTodoResize = true
  window.addEventListener('pointermove', handleTodoResizeMove)
  window.addEventListener('pointerup', stopTodoResize)
}

function handleTodoResizeMove(event: PointerEvent) {
  if (!activeTodoResize) return
  const container = (document.querySelector('.agent-col') as HTMLElement)
  if (!container) return
  const rect = container.getBoundingClientRect()
  const y = event.clientY - rect.top
  const ratio = y / rect.height
  if (ratio < TODO_COLLAPSE_THRESHOLD) {
    todoSidebarOpen.value = false
    return
  }
  if (ratio > 1 - TODO_COLLAPSE_THRESHOLD) {
    todoSidebarOpen.value = true
    todoSplitRatio.value = 1
    return
  }
  todoSidebarOpen.value = true
  todoSplitRatio.value = ratio
}

function stopTodoResize() {
  activeTodoResize = false
  window.removeEventListener('pointermove', handleTodoResizeMove)
  window.removeEventListener('pointerup', stopTodoResize)
}

function openAgentPage() {
  workspaceStore.setMainView('agent')
  fileSidebarOpen.value = false
  agentSidebarOpen.value = false
}

function toggleGraphView() {
  const next = workspaceStore.mainView === 'graph' ? 'editor' : 'graph'
  workspaceStore.setMainView(next)
  if (next !== 'editor') {
    fileSidebarOpen.value = false
    agentSidebarOpen.value = false
  }
}

function openDashboard() {
  const next = workspaceStore.mainView === 'dashboard' ? 'editor' : 'dashboard'
  workspaceStore.setMainView(next)
  if (next !== 'editor') {
    fileSidebarOpen.value = false
    agentSidebarOpen.value = false
  }
}

function openDebug() {
  const next = workspaceStore.mainView === 'debug' ? 'editor' : 'debug'
  workspaceStore.setMainView(next)
  if (next !== 'editor') {
    fileSidebarOpen.value = false
    agentSidebarOpen.value = false
  }
}

function openResources() {
  if (workspaceStore.mainView === 'resources') {
    workspaceStore.setMainView('editor')
    return
  }
  workspaceStore.setMainView('resources')
  fileSidebarOpen.value = false
  agentSidebarOpen.value = false
}

function openLibrary() {
  const next = workspaceStore.mainView === 'library' ? 'editor' : 'library'
  workspaceStore.setMainView(next)
  if (next !== 'editor') {
    fileSidebarOpen.value = false
    agentSidebarOpen.value = false
  }
}

function openIngestion() {
  const next = workspaceStore.mainView === 'ingestion' ? 'editor' : 'ingestion'
  workspaceStore.setMainView(next)
  if (next !== 'editor') {
    fileSidebarOpen.value = false
    agentSidebarOpen.value = false
  }
}

function openSearch() {
  const next = workspaceStore.mainView === 'search' ? 'editor' : 'search'
  workspaceStore.setMainView(next)
  if (next !== 'editor') {
    fileSidebarOpen.value = false
    agentSidebarOpen.value = false
  }
}

function openSettings() {
  const next = workspaceStore.mainView === 'settings' ? 'editor' : 'settings'
  workspaceStore.setMainView(next)
  if (next !== 'editor') {
    fileSidebarOpen.value = false
    agentSidebarOpen.value = false
  }
}

async function openGraphNode(node: KnowledgeGraphNodeEvent) {
  if (node.kind === 'root') {
    return
  }
  if (node.kind === 'virtual-group' && node.id.startsWith('library:')) {
    workspaceStore.openLibraryParent(node.id.slice('library:'.length))
    fileSidebarOpen.value = false
    agentSidebarOpen.value = false
    return
  }
  if (!node.path) {
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
  if (isAgentPage.value) {
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
    if (agentSidebarOpen.value) {
      agentSidebarOpen.value = false
    }
    return
  }
  if (!visibleAgentSidebarOpen.value) {
    agentSidebarOpen.value = true
  }
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
  stopTodoResize()
})
</script>

<template>
  <div class="workspace-page" :class="{ resizing: activeResizeTarget || activeTodoResize }">
    <TopCommandBar @toggle-agent="toggleAgentSidebar" @toggle-todo="toggleTodoSidebar" @open-agent-page="openAgentPage" @open-settings="openSettings" />
    <div
      ref="workspaceGrid"
      class="workspace-grid"
      :class="{
        'file-sidebar-collapsed': !visibleFileSidebarOpen,
        'agent-sidebar-collapsed': !visibleAgentSidebarOpen,
        'agent-main-view': isAgentPage,
        'graph-main-view': isGraphPage,
      }"
      :style="workspaceGridStyle"
    >
      <ActivityBar
        class="activity-col"
        :file-open="visibleFileSidebarOpen"
        :agent-open="visibleAgentSidebarOpen"
        :resources-active="workspaceStore.mainView === 'resources'"
        :library-active="workspaceStore.mainView === 'library'"
        :ingestion-active="workspaceStore.mainView === 'ingestion'"
        :agent-active="workspaceStore.mainView === 'agent'"
        :graph-active="workspaceStore.mainView === 'graph'"
        :dashboard-active="workspaceStore.mainView === 'dashboard'"
        :debug-active="workspaceStore.mainView === 'debug'"
        :search-active="workspaceStore.mainView === 'search'"
        :settings-active="workspaceStore.mainView === 'settings'"
        @toggle-file="toggleFileSidebar"
        @open-resources="openResources"
        @open-library="openLibrary"
        @open-ingestion="openIngestion"
        @toggle-agent="openAgentPage"
        @toggle-graph="toggleGraphView"
        @open-dashboard="openDashboard"
        @open-debug="openDebug"
        @open-search="openSearch"
        @open-settings="openSettings"
      />
      <FileTreePanel class="file-col ide-panel" :aria-hidden="!visibleFileSidebarOpen" />
      <div
        class="resize-handle file-resizer"
        role="separator"
        aria-label="Resize file tree"
        @pointerdown="startResize('file', $event)"
      ></div>
      <EditorPane v-if="workspaceStore.mainView === 'editor'" class="editor-col ide-panel" />
      <FileResourceManager v-else-if="workspaceStore.mainView === 'resources'" class="editor-col ide-panel" />
      <LibraryView v-else-if="workspaceStore.mainView === 'library'" class="editor-col ide-panel" />
      <IngestionProgressView v-else-if="workspaceStore.mainView === 'ingestion'" class="editor-col ide-panel" />
      <AgentPage v-else-if="workspaceStore.mainView === 'agent'" class="editor-col ide-panel" />
      <GraphPane v-else-if="workspaceStore.mainView === 'graph'" class="editor-col ide-panel" @open-node="openGraphNode" />
      <DashboardView v-else-if="workspaceStore.mainView === 'dashboard'" class="editor-col ide-panel" />
      <DebugView v-else-if="workspaceStore.mainView === 'debug'" class="editor-col ide-panel" />
      <SearchPage v-else-if="workspaceStore.mainView === 'search'" class="editor-col ide-panel" />
      <SettingsView v-else-if="workspaceStore.mainView === 'settings'" class="editor-col ide-panel" />
      <div
        class="resize-handle agent-resizer"
        role="separator"
        aria-label="Resize Agent panel"
        @pointerdown="startResize('agent', $event)"
      ></div>
      <div v-if="!isAgentPage" class="agent-col" :class="{ 'todo-open': todoSidebarOpen }" :aria-hidden="!visibleAgentSidebarOpen">
        <div class="todo-section" :style="{ flex: todoSidebarOpen ? (agentSidebarOpen ? todoSplitRatio : 1) : 0 }">
          <div class="todo-body-wrap" :class="{ visible: todoSidebarOpen }">
            <TodoSidebar />
          </div>
        </div>
        <div
          class="todo-agent-divider"
          :class="{ visible: todoSidebarOpen }"
          @pointerdown="startTodoResize"
        ></div>
        <div class="agent-section" :class="{ visible: agentSidebarOpen }" :style="{ flex: agentSidebarOpen ? (todoSidebarOpen ? 1 - todoSplitRatio : 1) : 0 }">
          <div class="agent-body-wrap" :class="{ visible: agentSidebarOpen }">
            <AgentPanel @expand="openAgentPage" />
          </div>
        </div>
      </div>
    </div>
    <CommandPalette />
    <SelectionToolbar @ask="handleAskAgent" />
    <FileConflictDialog v-if="showConflictDialog" />
    <ImagePreviewer />
  </div>
</template>

<style scoped>
.workspace-page {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  width: 100%;
  height: 100%;
  background: var(--color-bg-app);
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
  display: flex;
  flex-direction: column;
  min-height: 0;
  transition:
    opacity 160ms ease,
    transform 180ms ease;
}

.todo-section {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
  height: 100%;
}

.todo-body-wrap {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  overflow: hidden;
  opacity: 0;
  transform: translateY(-12px);
  transition: opacity 180ms ease, transform 180ms ease;
}

.todo-body-wrap.visible {
  opacity: 1;
  transform: translateY(0);
}

.agent-section {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}

.agent-body-wrap {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  overflow: hidden;
  opacity: 0;
  transform: translateY(12px);
  transition: opacity 180ms ease, transform 180ms ease;
}

.agent-body-wrap.visible {
  opacity: 1;
  transform: translateY(0);
}

.todo-agent-divider {
  flex: 0 0 4px;
  cursor: row-resize;
  background: transparent;
  border-top: 1px solid transparent;
  border-bottom: 1px solid transparent;
  opacity: 0;
  transition: opacity 160ms ease, background var(--transition-fast);
}

.todo-agent-divider.visible {
  opacity: 1;
}

.todo-agent-divider:hover,
.workspace-page.resizing .todo-agent-divider {
  background: var(--color-primary-soft);
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
  border-right: 0;
  border-radius: var(--radius-lg);
  background: var(--color-bg-app);
}

.agent-col {
  border-right: 0;
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
