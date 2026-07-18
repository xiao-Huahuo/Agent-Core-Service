<!--
  Knowledge file resource manager.

  Usage:
  Rendered as a center workspace page. It offers Explorer-style file browsing,
  view modes, range/discrete multi-selection, folder-size summaries, previews,
  and visible drop targets for external files.
-->
<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import {
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  ArrowUpDown,
  Ban,
  Check,
  CircleAlert,
  CircleCheck,
  FileArchive,
  FileCode2,
  FileImage,
  FileJson,
  FileSpreadsheet,
  FileText,
  Folder,
  FolderOpen,
  Grid2X2,
  Image as ImageIcon,
  LayoutList,
  List,
  ListChecks,
  RefreshCw,
  X,
} from 'lucide-vue-next'

import FileContextMenu from '@/components/editor_workspace/FileContextMenu.vue'
import {
  displayIngestedAt,
  displayMtime,
  extensionOf,
  fileKind,
  formatSize,
  isImageNode,
  nodeSize,
  normalizeTreePath,
  parentPath,
  timestampOf,
} from '@/components/editor_workspace/fileResourceManagerUtils'
import { previewKnowledgeFile, readKnowledgeFile } from '@/api/knowledge'
import { useSettingsStore } from '@/stores/settings'
import { useWorkspaceStore } from '@/stores/workspace'
import type { FilePreviewPayload, KnowledgeFileNode } from '@/types/knowledge'

defineOptions({ name: 'FileResourceManager' })

type ResourceViewMode = 'list' | 'content' | 'small' | 'medium' | 'large'
type SortKey = 'name' | 'mtime' | 'ingested' | 'size'
type SortDirection = 'asc' | 'desc'

const workspaceStore = useWorkspaceStore()
const settingsStore = useSettingsStore()
const currentDir = ref('')
const directoryBackStack = ref<string[]>([])
const directoryForwardStack = ref<string[]>([])
const viewMode = ref<ResourceViewMode>('list')
const multiSelectMode = ref(false)
const sortMenuOpen = ref(false)
const sortKey = ref<SortKey>('name')
const sortDirection = ref<SortDirection>('asc')
const switchingRoot = ref(false)
const rootError = ref('')
const dragging = ref(false)
const dragTargetPath = ref('')
const previewLoading = ref(false)
const previewError = ref('')
const previewPayloadByPath = ref<Record<string, FilePreviewPayload>>({})
const contentByPath = ref<Record<string, string>>({})
const imagePreviewUrls = ref<Record<string, string>>({})
const contextMenu = ref<{
  open: boolean
  x: number
  y: number
  node: KnowledgeFileNode | null
}>({ open: false, x: 0, y: 0, node: null })
const contextMenuStyle = ref<Record<string, string>>({ left: '0px', top: '0px' })
const contextMenuRef = ref<{ getBoundingClientRect: () => DOMRect } | null>(null)

const viewModes: { value: ResourceViewMode; label: string; title: string }[] = [
  { value: 'list', label: '列表', title: '详细列表' },
  { value: 'small', label: '小', title: '小图标' },
  { value: 'medium', label: '中', title: '中图标' },
  { value: 'large', label: '大', title: '大图标' },
]
const sortKeyOptions: { value: SortKey; label: string }[] = [
  { value: 'name', label: '名称排序' },
  { value: 'mtime', label: '修改时间排序' },
  { value: 'ingested', label: '入库时间排序' },
  { value: 'size', label: '大小排序' },
]
const sortDirectionOptions: { value: SortDirection; label: string }[] = [
  { value: 'asc', label: '递增' },
  { value: 'desc', label: '递减' },
]

const flatNodes = computed(() => workspaceStore.flatNodes)
const selectedPaths = computed(() => workspaceStore.selectedTreePaths)
const isMultiSelecting = computed(() => multiSelectMode.value || selectedPaths.value.size > 0)
const canPaste = computed(() => Boolean(workspaceStore.fileClipboard) || Boolean(window.agentEditorDesktop?.readClipboardFilePaths))
const selectedNode = computed(() => flatNodes.value.find((node) => node.path === workspaceStore.selectedTreePath) ?? null)
const selectedPreviewPayload = computed(() => {
  const path = selectedNode.value?.path ?? ''
  return path ? previewPayloadByPath.value[path] ?? workspaceStore.activePreview : null
})
const selectedContent = computed(() => {
  const path = selectedNode.value?.path ?? ''
  return path ? contentByPath.value[path] ?? workspaceStore.activeContent : ''
})

const canGoBack = computed(() => directoryBackStack.value.length > 0)
const canGoForward = computed(() => directoryForwardStack.value.length > 0)
const canGoUp = computed(() => Boolean(currentDir.value))
const pathCapsuleParts = computed(() => {
  const parts = currentDir.value.split('/').filter(Boolean)
  return [
    { label: '根目录', path: '' },
    ...parts.map((part, index) => ({
      label: part,
      path: parts.slice(0, index + 1).join('/'),
    })),
  ]
})

const visibleItems = computed(() => {
  const targetParent = currentDir.value
  return flatNodes.value
    .filter((node) => parentPath(node.path) === targetParent)
    .sort(compareNodes)
})

const listGridColumns = computed(() => {
  const selectionColumn = isMultiSelecting.value ? '28px ' : ''
  const indexColumn = settingsStore.showIndexColumn ? '118px' : ''
  return `${selectionColumn}minmax(240px, 1fr) 168px 168px 112px 96px${indexColumn ? ` ${indexColumn}` : ''}`
})

watch(
  () => workspaceStore.selectedTreePath,
  () => {
    if (viewMode.value === 'content') {
      void ensureSelectedPreview()
    }
  },
)

watch(
  [visibleItems, viewMode],
  () => {
    if (viewMode.value === 'large') {
      void ensureLargeImagePreviews()
    }
  },
  { immediate: true },
)

function joinAbsoluteKnowledgePath(relativePath: string): string {
  const root = settingsStore.profile.knowledgeDir.replace(/[\\/]+$/g, '')
  const child = normalizeTreePath(relativePath)
  if (!child) {
    return root
  }
  return `${root}\\${child.replace(/\//g, '\\')}`
}

function contextTargetDir(): string {
  const node = contextMenu.value.node
  if (!node) {
    return currentDir.value
  }
  return node.isDir ? node.path : parentPath(node.path)
}

function compareNodes(a: KnowledgeFileNode, b: KnowledgeFileNode): number {
  const dirOrder = Number(b.isDir) - Number(a.isDir)
  if (dirOrder !== 0) {
    return dirOrder
  }
  let result = 0
  if (sortKey.value === 'name') {
    result = a.name.localeCompare(b.name)
  } else if (sortKey.value === 'mtime') {
    result = timestampOf(a.mtime) - timestampOf(b.mtime)
  } else if (sortKey.value === 'ingested') {
    result = timestampOf(displayIngestedAt(a)) - timestampOf(displayIngestedAt(b))
  } else {
    result = nodeSize(a) - nodeSize(b)
  }
  if (result === 0) {
    result = a.name.localeCompare(b.name)
  }
  return sortDirection.value === 'asc' ? result : -result
}

async function openRootPicker() {
  rootError.value = ''
  if (!window.agentEditorDesktop?.selectDirectory) {
    rootError.value = 'Switching a local knowledge root requires the Electron directory picker.'
    workspaceStore.showToast(rootError.value)
    return
  }
  const selectedDir = await window.agentEditorDesktop.selectDirectory()
  if (!selectedDir) {
    return
  }
  switchingRoot.value = true
  try {
    await settingsStore.switchKnowledgeRoot(selectedDir)
    currentDir.value = ''
    directoryBackStack.value = []
    directoryForwardStack.value = []
    workspaceStore.clearTreeSelection()
  } catch (error) {
    rootError.value = error instanceof Error ? error.message : 'Failed to switch knowledge root.'
    workspaceStore.showToast(rootError.value)
  } finally {
    await workspaceStore.loadKnowledgeTree()
    workspaceStore.restartFileWatcher()
    switchingRoot.value = false
  }
}

function navigateToDirectory(path: string, recordHistory = true) {
  const normalizedPath = normalizeTreePath(path)
  if (normalizedPath === currentDir.value) {
    return
  }
  if (recordHistory) {
    directoryBackStack.value = [...directoryBackStack.value, currentDir.value]
    directoryForwardStack.value = []
  }
  currentDir.value = normalizedPath
  workspaceStore.clearTreeSelection()
}

function goBackDirectory() {
  const previousPath = directoryBackStack.value[directoryBackStack.value.length - 1]
  if (previousPath === undefined) {
    return
  }
  directoryBackStack.value = directoryBackStack.value.slice(0, -1)
  directoryForwardStack.value = [...directoryForwardStack.value, currentDir.value]
  navigateToDirectory(previousPath, false)
}

function goForwardDirectory() {
  const nextPath = directoryForwardStack.value[directoryForwardStack.value.length - 1]
  if (nextPath === undefined) {
    return
  }
  directoryForwardStack.value = directoryForwardStack.value.slice(0, -1)
  directoryBackStack.value = [...directoryBackStack.value, currentDir.value]
  navigateToDirectory(nextPath, false)
}

function goUpDirectory() {
  if (!currentDir.value) {
    return
  }
  navigateToDirectory(parentPath(currentDir.value))
}

async function refreshResources() {
  await workspaceStore.loadKnowledgeTree()
  if (!flatNodes.value.some((node) => node.path === currentDir.value) && currentDir.value) {
    navigateToDirectory('', false)
  }
}

function iconForNode(node: KnowledgeFileNode) {
  if (node.isDir) return Folder
  const ext = extensionOf(node.name)
  if (['js', 'jsx', 'ts', 'tsx', 'vue', 'html', 'css', 'scss', 'py', 'go', 'rs', 'java'].includes(ext)) return FileCode2
  if (['json', 'jsonl', 'yaml', 'yml', 'xml'].includes(ext)) return FileJson
  if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'].includes(ext)) return FileImage
  if (['csv', 'xls', 'xlsx', 'tsv'].includes(ext)) return FileSpreadsheet
  if (['zip', 'rar', '7z', 'tar', 'gz'].includes(ext)) return FileArchive
  return FileText
}

function iconClassForNode(node: KnowledgeFileNode): string {
  if (node.isDir) return 'kind-folder'
  const ext = extensionOf(node.name)
  if (['md', 'markdown'].includes(ext)) return 'kind-markdown'
  if (['js', 'jsx', 'ts', 'tsx', 'vue', 'html', 'css', 'scss'].includes(ext)) return 'kind-web'
  if (['py', 'go', 'rs', 'java'].includes(ext)) return 'kind-code'
  if (['json', 'jsonl', 'yaml', 'yml', 'xml'].includes(ext)) return 'kind-data'
  if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'].includes(ext)) return 'kind-image'
  if (['csv', 'xls', 'xlsx', 'tsv'].includes(ext)) return 'kind-sheet'
  if (['zip', 'rar', '7z', 'tar', 'gz'].includes(ext)) return 'kind-archive'
  return 'kind-default'
}

function indexStatusIcon(node: KnowledgeFileNode) {
  if (node.indexStatus === 'indexed' || node.indexStatus === 'clean') return CircleCheck
  if (node.indexStatus === 'ignored') return Ban
  return CircleAlert
}

function indexStatusTitle(node: KnowledgeFileNode): string {
  if (node.indexStatus === 'indexed' || node.indexStatus === 'clean') return '已进入向量库'
  if (node.indexStatus === 'ignored') return '已屏蔽'
  if (node.indexStatus === 'failed') return '入库失败'
  return '未进入向量库'
}

function indexStatusClass(node: KnowledgeFileNode): string {
  if (node.indexStatus === 'indexed' || node.indexStatus === 'clean') return 'indexed'
  if (node.indexStatus === 'ignored') return 'ignored'
  if (node.indexStatus === 'failed') return 'failed'
  return 'dirty'
}

function visibleRangePaths(anchorPath: string, targetPath: string): string[] {
  const paths = visibleItems.value.map((node) => node.path)
  const anchorIndex = paths.indexOf(anchorPath)
  const targetIndex = paths.indexOf(targetPath)
  if (anchorIndex < 0 || targetIndex < 0) {
    return [targetPath]
  }
  const start = Math.min(anchorIndex, targetIndex)
  const end = Math.max(anchorIndex, targetIndex)
  return paths.slice(start, end + 1)
}

function handleItemClick(node: KnowledgeFileNode, event: MouseEvent) {
  if (event.shiftKey) {
    workspaceStore.selectTreeNode(node, {
      rangePaths: visibleRangePaths(workspaceStore.selectionAnchorPath || workspaceStore.selectedTreePath, node.path),
    })
    return
  }
  if (event.ctrlKey || event.metaKey) {
    workspaceStore.selectTreeNode(node, { additive: true })
    return
  }
  if (isMultiSelecting.value) {
    workspaceStore.selectTreeNode(node, { additive: true })
    return
  }
  workspaceStore.selectTreeNode(node)
  if (!node.isDir) {
    void workspaceStore.selectFile(node)
    if (viewMode.value === 'content') {
      void ensureSelectedPreview()
    }
  }
}

function handleItemDblClick(node: KnowledgeFileNode) {
  if (node.isDir) {
    navigateToDirectory(node.path)
    workspaceStore.selectedTreePath = node.path
    return
  }
  workspaceStore.setMainView('editor')
  void workspaceStore.selectFile(node)
}

function selectBreadcrumb(path: string) {
  navigateToDirectory(path)
}

function cancelMultiSelection() {
  multiSelectMode.value = false
  workspaceStore.clearTreeSelection()
}

function toggleMultiSelectMode() {
  multiSelectMode.value = !multiSelectMode.value
  if (!multiSelectMode.value) {
    workspaceStore.clearTreeSelection()
  }
}

function selectSortKey(value: SortKey) {
  sortKey.value = value
}

function selectSortDirection(value: SortDirection) {
  sortDirection.value = value
  sortMenuOpen.value = false
}

async function openContextMenu(node: KnowledgeFileNode | null, event: MouseEvent) {
  if (node && !workspaceStore.selectedTreePaths.has(node.path)) {
    workspaceStore.selectTreeNode(node)
  }
  const rawX = event.clientX
  const rawY = event.clientY
  contextMenu.value = { open: true, x: rawX, y: rawY, node }
  contextMenuStyle.value = { left: `${rawX}px`, top: `${rawY}px` }
  await nextTick()
  const menu = contextMenuRef.value
  if (!menu) return
  const rect = menu.getBoundingClientRect()
  const vw = window.innerWidth
  const vh = window.innerHeight
  const overflowRight = Math.max(0, rect.right - vw)
  const overflowBottom = Math.max(0, rect.bottom - vh)
  if (overflowRight > 0 || overflowBottom > 0) {
    contextMenuStyle.value = {
      left: `${Math.max(0, rawX - overflowRight)}px`,
      top: `${Math.max(0, rawY - overflowBottom)}px`,
    }
  }
}

function closeContextMenu() {
  contextMenu.value.open = false
}

function contextTargetNodes(): KnowledgeFileNode[] {
  const node = contextMenu.value.node
  if (!node) {
    return []
  }
  if (!workspaceStore.selectedTreePaths.has(node.path)) {
    return [node]
  }
  return workspaceStore.getSelectedTreeNodes(node)
}

async function writeClipboardText(text: string) {
  if (window.agentEditorDesktop?.writeClipboardText) {
    await window.agentEditorDesktop.writeClipboardText(text)
    return
  }
  await navigator.clipboard?.writeText(text)
}

async function createFileFromMenu() {
  const name = window.prompt('新建文件名', 'untitled.md')?.trim()
  const parentDir = contextTargetDir()
  closeContextMenu()
  if (name) {
    await workspaceStore.createFileAt(parentDir, name)
  }
}

async function createFolderFromMenu() {
  const name = window.prompt('新建文件夹名', 'New Folder')?.trim()
  const parentDir = contextTargetDir()
  closeContextMenu()
  if (name) {
    await workspaceStore.createFolderAt(parentDir, name)
  }
}

async function copyFromMenu() {
  const node = contextMenu.value.node
  closeContextMenu()
  if (node) await workspaceStore.copyNode(node)
}

async function cutFromMenu() {
  const node = contextMenu.value.node
  closeContextMenu()
  if (node) await workspaceStore.cutNode(node)
}

async function copyNameFromMenu() {
  const node = contextMenu.value.node
  closeContextMenu()
  if (node) await writeClipboardText(node.name)
}

async function copyAbsolutePathFromMenu() {
  const node = contextMenu.value.node
  closeContextMenu()
  if (node) await writeClipboardText(joinAbsoluteKnowledgePath(node.path))
}

async function copyRelativePathFromMenu() {
  const node = contextMenu.value.node
  closeContextMenu()
  if (node) await writeClipboardText(node.path)
}

async function pasteFromMenu() {
  const node = contextMenu.value.node
  closeContextMenu()
  await workspaceStore.pasteNode(node, 'resources')
}

async function renameFromMenu() {
  const node = contextMenu.value.node
  if (!node) {
    closeContextMenu()
    return
  }
  const nextName = window.prompt('重命名', node.name)?.trim()
  closeContextMenu()
  if (nextName) {
    await workspaceStore.renameNode(node, nextName)
  }
}

async function showInFolderFromMenu() {
  const node = contextMenu.value.node
  const absolutePath = node ? joinAbsoluteKnowledgePath(node.path) : settingsStore.profile.knowledgeDir
  closeContextMenu()
  await window.agentEditorDesktop?.showItemInFolder?.(absolutePath)
}

async function openWithDefaultFromMenu() {
  const node = contextMenu.value.node
  const absolutePath = node ? joinAbsoluteKnowledgePath(node.path) : settingsStore.profile.knowledgeDir
  closeContextMenu()
  await window.agentEditorDesktop?.openPath?.(absolutePath)
}

function showInGraphFromMenu() {
  closeContextMenu()
  workspaceStore.setMainView('graph')
}

async function askAgentFromMenu() {
  const node = contextMenu.value.node
  closeContextMenu()
  workspaceStore.setMainView('editor')
  if (node && !node.isDir) {
    await workspaceStore.selectFile(node)
    workspaceStore.syncCurrentDocumentContext()
    workspaceStore.agentSidebarOpen = true
    workspaceStore.pendingAgentPrompt = 'Help me review the currently open file.'
  }
}

async function ingestFromMenu() {
  const nodes = contextTargetNodes()
  closeContextMenu()
  for (const node of nodes) {
    await workspaceStore.ingestFile(node)
  }
}

function ignorePatternForNode(node: KnowledgeFileNode): string {
  const normalizedPath = normalizeTreePath(node.path)
  return node.isDir ? `${normalizedPath}/` : normalizedPath
}

function normalizeIgnorePatternLine(line: string): string {
  return line.replace(/\\/g, '/').trim()
}

async function toggleIgnoreFromMenu() {
  const nodes = contextTargetNodes()
  closeContextMenu()
  if (nodes.length === 0) return
  let currentLines = (settingsStore.profile.knowledgeIgnorePatterns ?? '')
    .split(/\r?\n/)
    .map((line) => line.trimEnd())
    .filter((line) => line.trim().length > 0)
  for (const node of nodes) {
    const pattern = ignorePatternForNode(node)
    const isCurrentlyIgnored = node.indexStatus === 'ignored'
    currentLines = isCurrentlyIgnored
      ? currentLines.filter((line) => normalizeIgnorePatternLine(line) !== pattern)
      : [...currentLines.filter((line) => normalizeIgnorePatternLine(line) !== `!${pattern}`), pattern]
  }
  await settingsStore.saveKnowledgeIngestionSettings({ knowledgeIgnorePatterns: currentLines.join('\n') })
  await workspaceStore.loadKnowledgeTree()
}

async function deleteFromMenu() {
  const nodes = contextTargetNodes()
  closeContextMenu()
  const firstNode = nodes[0]
  if (nodes.length === 1 && firstNode && window.confirm(`删除 ${firstNode.name}?`)) {
    await workspaceStore.deleteNode(firstNode)
    return
  }
  if (nodes.length > 1 && window.confirm(`删除选中的 ${nodes.length} 项?`)) {
    for (const node of nodes) {
      await workspaceStore.deleteNode(node)
    }
  }
}

async function ensureSelectedPreview() {
  const node = selectedNode.value
  if (!node || node.isDir) {
    return
  }
  previewError.value = ''
  previewLoading.value = true
  try {
    await workspaceStore.selectFile(node)
    if (contentByPath.value[node.path] === undefined) {
      const response = await readKnowledgeFile(settingsStore.profile.userId, node.path)
      contentByPath.value = { ...contentByPath.value, [node.path]: response.content }
    }
  } catch {
    try {
      const preview = await previewKnowledgeFile(settingsStore.profile.userId, node.path)
      previewPayloadByPath.value = { ...previewPayloadByPath.value, [node.path]: preview }
      if (preview.content !== undefined) {
        contentByPath.value = { ...contentByPath.value, [node.path]: preview.content }
      }
    } catch (error) {
      previewError.value = error instanceof Error ? error.message : '内容预览加载失败'
    }
  } finally {
    previewLoading.value = false
  }
}

async function ensureLargeImagePreviews() {
  const images = visibleItems.value.filter((node) => isImageNode(node) && !imagePreviewUrls.value[node.path])
  if (images.length === 0) {
    return
  }
  for (const node of images.slice(0, 24)) {
    try {
      const preview = await previewKnowledgeFile(settingsStore.profile.userId, node.path)
      if (preview.data_url || preview.raw_url) {
        imagePreviewUrls.value = { ...imagePreviewUrls.value, [node.path]: preview.data_url || preview.raw_url || '' }
      }
    } catch {
      imagePreviewUrls.value = { ...imagePreviewUrls.value, [node.path]: '' }
    }
  }
}

function filesFromEvent(event: DragEvent): File[] {
  return Array.from(event.dataTransfer?.files ?? [])
}

function desktopPathsFromFiles(files: File[]): string[] {
  const getPathForFile = window.agentEditorDesktop?.getPathForFile
  if (!getPathForFile) {
    return []
  }
  return files
    .map((file) => {
      try {
        return getPathForFile(file)
      } catch {
        return ''
      }
    })
    .filter(Boolean)
}

function handleDragEnter(path = currentDir.value) {
  dragging.value = true
  dragTargetPath.value = path
}

function handleDragLeave(event: DragEvent) {
  const el = event.currentTarget as HTMLElement | null
  const related = event.relatedTarget as HTMLElement | null
  if (el && related && el.contains(related)) return
  dragging.value = false
  dragTargetPath.value = ''
}

async function handleDrop(event: DragEvent, targetNode?: KnowledgeFileNode) {
  dragging.value = false
  const targetDir = targetNode?.isDir ? targetNode.path : currentDir.value
  dragTargetPath.value = ''
  const files = filesFromEvent(event)
  if (files.length === 0) {
    return
  }
  const desktopPaths = desktopPathsFromFiles(files)
  if (desktopPaths.length > 0) {
    await workspaceStore.importExternalPathsToPath(desktopPaths, targetDir, undefined, 'resources')
    multiSelectMode.value = false
    workspaceStore.clearTreeSelection()
    workspaceStore.selectedTreePath = targetDir
    return
  }
  await workspaceStore.importFilesToPath(files, targetDir, undefined, 'resources')
  multiSelectMode.value = false
  workspaceStore.clearTreeSelection()
  workspaceStore.selectedTreePath = targetDir
}

function previewSummary(node: KnowledgeFileNode): string {
  if (node.isDir) {
    return `${node.children?.length ?? 0} 项, ${formatSize(nodeSize(node))}`
  }
  const text = contentByPath.value[node.path]
  if (text) {
    return text.replace(/\s+/g, ' ').trim().slice(0, 180)
  }
  return `${fileKind(node)} | ${formatSize(nodeSize(node))}`
}

onMounted(() => {
  document.addEventListener('click', closeContextMenu)
})

onUnmounted(() => {
  document.removeEventListener('click', closeContextMenu)
})
</script>

<template>
  <section
    class="resource-manager"
    :class="{ dragging, 'theme-dark': settingsStore.isDark }"
    @dragenter.prevent="handleDragEnter()"
    @dragover.prevent="handleDragEnter()"
    @dragleave="handleDragLeave"
    @drop.prevent="handleDrop"
    @contextmenu.prevent="openContextMenu(null, $event)"
  >
    <header class="resource-toolbar">
      <div class="nav-controls" aria-label="Folder navigation">
        <button class="tool-button" type="button" title="回退" :disabled="!canGoBack" @click="goBackDirectory">
          <ArrowLeft :size="15" />
        </button>
        <button class="tool-button" type="button" title="反回退" :disabled="!canGoForward" @click="goForwardDirectory">
          <ArrowRight :size="15" />
        </button>
        <button class="tool-button" type="button" title="去上级文件夹" :disabled="!canGoUp" @click="goUpDirectory">
          <ArrowUp :size="15" />
        </button>
        <button class="tool-button" type="button" title="刷新" @click="refreshResources">
          <RefreshCw :size="15" />
        </button>
      </div>
      <span class="toolbar-separator"></span>
      <button
        class="root-button"
        type="button"
        :disabled="switchingRoot"
        :title="rootError || 'Switch knowledge root'"
        @click="openRootPicker"
      >
        <FolderOpen :size="18" />
      </button>
      <div class="path-capsule" aria-label="Current path">
        <button
          v-for="part in pathCapsuleParts"
          :key="part.path || '__root'"
          class="path-part"
          type="button"
          @click="selectBreadcrumb(part.path)"
        >
          {{ part.label }}
        </button>
      </div>
      <button
        class="tool-button"
        :class="{ active: multiSelectMode }"
        type="button"
        title="多选"
        aria-label="多选"
        @click="toggleMultiSelectMode"
      >
        <ListChecks :size="15" />
      </button>
      <div class="sort-control">
        <button
          class="tool-button"
          :class="{ active: sortMenuOpen }"
          type="button"
          title="排序"
          aria-label="排序"
          @click="sortMenuOpen = !sortMenuOpen"
        >
          <ArrowUpDown :size="15" />
        </button>
        <div v-if="sortMenuOpen" class="sort-menu" @click.stop>
          <button
            v-for="option in sortKeyOptions"
            :key="option.value"
            type="button"
            @click="selectSortKey(option.value)"
          >
            <Check v-if="sortKey === option.value" :size="14" />
            <span v-else class="sort-check-placeholder"></span>
            <span class="sort-icon-placeholder"></span>
            <span>{{ option.label }}</span>
          </button>
          <hr />
          <button
            v-for="option in sortDirectionOptions"
            :key="option.value"
            type="button"
            @click="selectSortDirection(option.value)"
          >
            <Check v-if="sortDirection === option.value" :size="14" />
            <span v-else class="sort-check-placeholder"></span>
            <ArrowUp v-if="option.value === 'asc'" :size="14" />
            <ArrowDown v-else :size="14" />
            <span>{{ option.label }}</span>
          </button>
        </div>
      </div>
      <div class="view-switch" aria-label="View mode">
        <button
          v-for="mode in viewModes"
          :key="mode.value"
          class="view-button"
          :class="{ active: viewMode === mode.value }"
          type="button"
          :title="mode.title"
          @click="viewMode = mode.value"
        >
          <List v-if="mode.value === 'list'" :size="15" />
          <LayoutList v-else-if="mode.value === 'small'" :size="15" />
          <Grid2X2 v-else-if="mode.value === 'medium'" :size="15" />
          <ImageIcon v-else :size="15" />
          <span>{{ mode.label }}</span>
        </button>
      </div>
    </header>

    <div v-if="isMultiSelecting" class="multi-banner">
      <span>{{ selectedPaths.size > 0 ? `已选择 ${selectedPaths.size} 项` : '多选模式' }}</span>
      <button class="banner-close" type="button" title="取消多选" @click="cancelMultiSelection">
        <X :size="15" />
      </button>
    </div>

    <div class="content-shell" :class="`mode-${viewMode}`">
      <div v-if="viewMode === 'list'" class="list-view">
        <div class="list-header" :style="{ gridTemplateColumns: listGridColumns }">
          <span v-if="isMultiSelecting" class="selection-column-header"></span>
          <span>名称</span>
          <span>最后修改日期</span>
          <span>入库日期</span>
          <span>类型</span>
          <span>大小</span>
          <span v-if="settingsStore.showIndexColumn">入库状态</span>
        </div>
        <button
          v-for="(node, index) in visibleItems"
          :key="node.path"
          class="resource-row"
          :class="{ selected: workspaceStore.selectedTreePath === node.path || selectedPaths.has(node.path) }"
          :style="{
            gridTemplateColumns: listGridColumns,
            animationDelay: `${Math.min(index, 24) * 18}ms`,
          }"
          type="button"
          draggable="true"
          @click="handleItemClick(node, $event)"
          @dblclick="handleItemDblClick(node)"
          @dragenter.prevent="node.isDir && handleDragEnter(node.path)"
          @dragover.prevent="node.isDir && handleDragEnter(node.path)"
          @drop.prevent.stop="handleDrop($event, node)"
          @contextmenu.prevent.stop="openContextMenu(node, $event)"
        >
          <span v-if="isMultiSelecting" class="selection-check" :class="{ checked: selectedPaths.has(node.path) }">
            <Check v-if="selectedPaths.has(node.path)" :size="12" />
          </span>
          <span class="name-cell">
            <component :is="iconForNode(node)" :size="16" class="kind-icon" :class="iconClassForNode(node)" />
            <span class="file-name">{{ node.name }}</span>
          </span>
          <span>{{ displayMtime(node) }}</span>
          <span>{{ displayIngestedAt(node) }}</span>
          <span>{{ fileKind(node) }}</span>
          <span>{{ formatSize(nodeSize(node)) }}</span>
          <span v-if="settingsStore.showIndexColumn" class="index-status-cell" :class="indexStatusClass(node)">
            <component v-if="!node.isDir" :is="indexStatusIcon(node)" :size="13" />
            <span>{{ node.isDir ? '-' : indexStatusTitle(node) }}</span>
          </span>
        </button>
      </div>

      <div v-else-if="viewMode === 'content'" class="content-view">
        <div class="content-list">
          <button
            v-for="node in visibleItems"
            :key="node.path"
            class="content-item"
            :class="{ selected: workspaceStore.selectedTreePath === node.path || selectedPaths.has(node.path) }"
            type="button"
            @click="handleItemClick(node, $event)"
            @dblclick="handleItemDblClick(node)"
            @contextmenu.prevent.stop="openContextMenu(node, $event)"
          >
            <component :is="iconForNode(node)" :size="24" class="kind-icon" :class="iconClassForNode(node)" />
            <span class="content-text">
              <strong>{{ node.name }}</strong>
              <small>{{ previewSummary(node) }}</small>
            </span>
          </button>
        </div>
        <aside class="preview-pane">
          <div v-if="!selectedNode" class="preview-empty">选择一个文件查看内容</div>
          <div v-else-if="selectedNode.isDir" class="preview-empty">文件夹包含 {{ selectedNode.children?.length ?? 0 }} 项</div>
          <div v-else-if="previewLoading" class="preview-empty">正在加载内容</div>
          <div v-else-if="previewError" class="preview-empty">{{ previewError }}</div>
          <img
            v-else-if="selectedPreviewPayload?.data_url || selectedPreviewPayload?.raw_url"
            class="preview-image"
            :src="selectedPreviewPayload.data_url || selectedPreviewPayload.raw_url"
            :alt="selectedNode.name"
          />
          <div v-else-if="selectedPreviewPayload?.html" class="preview-html" v-html="selectedPreviewPayload.html"></div>
          <pre v-else class="preview-text">{{ selectedContent || selectedPreviewPayload?.message || '暂无可显示内容' }}</pre>
        </aside>
      </div>

      <div v-else class="icon-view" :class="`icon-${viewMode}`">
        <button
          v-for="node in visibleItems"
          :key="node.path"
          class="icon-tile"
          :class="{
            selected: workspaceStore.selectedTreePath === node.path || selectedPaths.has(node.path),
            glass: viewMode === 'medium' || viewMode === 'large',
          }"
          type="button"
          @click="handleItemClick(node, $event)"
          @dblclick="handleItemDblClick(node)"
          @dragenter.prevent="node.isDir && handleDragEnter(node.path)"
          @dragover.prevent="node.isDir && handleDragEnter(node.path)"
          @drop.prevent.stop="handleDrop($event, node)"
          @contextmenu.prevent.stop="openContextMenu(node, $event)"
        >
          <span v-if="isMultiSelecting" class="selection-check tile-selection-check" :class="{ checked: selectedPaths.has(node.path) }">
            <Check v-if="selectedPaths.has(node.path)" :size="12" />
          </span>
          <span class="tile-art">
            <img
              v-if="viewMode === 'large' && isImageNode(node) && imagePreviewUrls[node.path]"
              class="tile-image"
              :src="imagePreviewUrls[node.path]"
              :alt="node.name"
            />
            <ImageIcon v-else-if="viewMode === 'large' && isImageNode(node)" :size="54" class="kind-icon kind-image" />
            <component
              v-else
              :is="iconForNode(node)"
              :size="viewMode === 'small' ? 18 : (viewMode === 'large' ? 54 : 36)"
              class="kind-icon"
              :class="iconClassForNode(node)"
            />
          </span>
          <span class="tile-name">{{ node.name }}</span>
          <small v-if="viewMode !== 'small'">{{ formatSize(nodeSize(node)) }}</small>
        </button>
      </div>
    </div>

    <div v-if="dragging" class="drop-overlay" aria-live="polite">
      <div class="drop-box">
        <strong>拖拽到这里导入</strong>
        <span>目标: {{ dragTargetPath || currentDir || settingsStore.profile.knowledgeDir }}</span>
      </div>
    </div>
    <FileContextMenu
      v-if="contextMenu.open"
      ref="contextMenuRef"
      :node="contextMenu.node"
      :can-paste="canPaste"
      :menu-style="contextMenuStyle"
      @create-file="createFileFromMenu"
      @create-folder="createFolderFromMenu"
      @copy="copyFromMenu"
      @cut="cutFromMenu"
      @copy-name="copyNameFromMenu"
      @copy-absolute-path="copyAbsolutePathFromMenu"
      @copy-relative-path="copyRelativePathFromMenu"
      @paste="pasteFromMenu"
      @rename="renameFromMenu"
      @show-in-folder="showInFolderFromMenu"
      @open-default="openWithDefaultFromMenu"
      @show-in-graph="showInGraphFromMenu"
      @ask-agent="askAgentFromMenu"
      @ingest="ingestFromMenu"
      @toggle-ignore="toggleIgnoreFromMenu"
      @delete="deleteFromMenu"
    />
  </section>
</template>

<style src="./FileResourceManager.css" scoped></style>
