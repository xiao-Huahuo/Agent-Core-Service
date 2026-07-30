<!--
  File tree panel.

  Usage:
  Displays the current knowledge root, recursive file tree, drag-and-drop
  upload target, and watcher/index status placeholders.
-->
<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { ArrowLeft, ArrowUpDown, ArrowUp, ArrowDown, Check, ChevronsUpDown, FilePlus2, FolderPlus, History, ListFilter, RefreshCw, Search } from 'lucide-vue-next'

import FileContextMenu from '@/components/editor_workspace/FileContextMenu.vue'
import RecentFileList from '@/components/editor_workspace/RecentFileList.vue'
import TreeNode from '@/components/editor_workspace/TreeNode.vue'
import { useSettingsStore } from '@/stores/settings'
import { useWorkspaceStore } from '@/stores/workspace'
import type { KnowledgeFileNode } from '@/types/knowledge'
import { buildRecentFileGroups, type RecentFileVisit } from '@/utils/recentFileHistory'

const settingsStore = useSettingsStore()
const isDark = computed(() => settingsStore.isDark)
const workspaceStore = useWorkspaceStore()
const dragging = ref(false)
const uploadPicker = ref<HTMLInputElement | null>(null)
const contextMenu = ref<{
  open: boolean
  x: number
  y: number
  node: KnowledgeFileNode | null
}>({ open: false, x: 0, y: 0, node: null })
const contextMenuStyle = ref<Record<string, string>>({ left: '0px', top: '0px' })
const contextMenuRef = ref<{ getBoundingClientRect: () => DOMRect } | null>(null)
const treeVersion = ref(0)
const sortMenuOpen = ref(false)
const sortKey = ref<'name' | 'mtime' | 'ingested' | 'size'>('name')
const sortDirection = ref<'asc' | 'desc'>('asc')
/** Whether the panel is displaying the recent-files layout. */
const recentMode = ref(false)
/** Filename-only query applied to the frozen recent visit snapshot. */
const recentSearchQuery = ref('')
/** Stable visit ordering captured on entry or explicit refresh. */
const recentVisitSnapshot = ref<RecentFileVisit[]>([])
const recentFileGroups = computed(() => buildRecentFileGroups(
  recentVisitSnapshot.value,
  workspaceStore.flatNodes,
  recentSearchQuery.value,
))
const hasRecentFiles = computed(() => buildRecentFileGroups(
  recentVisitSnapshot.value,
  workspaceStore.flatNodes,
  '',
).length > 0)

function sortTreeNodes(nodes: KnowledgeFileNode[]): KnowledgeFileNode[] {
  const dirOrder = (a: KnowledgeFileNode, b: KnowledgeFileNode) => Number(b.isDir) - Number(a.isDir)
  const cmp = (a: KnowledgeFileNode, b: KnowledgeFileNode) => {
    const d = dirOrder(a, b)
    if (d !== 0) return d
    let r = 0
    if (sortKey.value === 'name') {
      r = a.name.localeCompare(b.name)
    } else if (sortKey.value === 'mtime') {
      r = (a.mtime ? new Date(a.mtime).getTime() : 0) - (b.mtime ? new Date(b.mtime).getTime() : 0)
    } else if (sortKey.value === 'ingested') {
      r = (a.ingestedAt ? new Date(a.ingestedAt).getTime() : 0) - (b.ingestedAt ? new Date(b.ingestedAt).getTime() : 0)
    } else {
      r = (a.size ?? 0) - (b.size ?? 0)
    }
    return sortDirection.value === 'asc' ? r : -r
  }
  return nodes
    .map((n) => ({ ...n, children: n.children ? sortTreeNodes(n.children) : n.children }))
    .sort(cmp)
}

const sortedTree = computed(() => {
  if (!workspaceStore.tree.length) return workspaceStore.tree
  return sortTreeNodes(workspaceStore.tree)
})
const inlineEdit = ref<{
  mode: 'create' | 'rename'
  kind: 'file' | 'folder'
  path: string
  parentPath: string
  value: string
  node: KnowledgeFileNode | null
} | null>(null)
const deleteTarget = ref<KnowledgeFileNode | null>(null)
const actionError = ref('')
const selectedTreePath = computed(() => workspaceStore.selectedTreePath || workspaceStore.selectedPath)
const canPaste = computed(() => Boolean(workspaceStore.fileClipboard) || Boolean(window.agentEditorDesktop?.readClipboardFilePaths))
const selectedTreeNode = computed(() => findNode(workspaceStore.tree, selectedTreePath.value))
const visibleTreeNodes = computed(() => flattenVisibleNodes(displayTree.value, workspaceStore.expandedPaths))
const displayTree = computed(() => {
  const edit = inlineEdit.value
  const source = edit?.mode === 'create'
    ? insertDraftNode(sortedTree.value, edit.parentPath, {
        name: edit.value,
        path: edit.path,
        isDir: edit.kind === 'folder',
        children: edit.kind === 'folder' ? [] : undefined,
        indexStatus: 'dirty',
      })
    : sortedTree.value
  return source
})

function normalizeTreePath(path: string): string {
  return path.replace(/\\/g, '/').replace(/^\/+|\/+$/g, '')
}

function getParentPath(path: string): string {
  const parts = normalizeTreePath(path).split('/').filter(Boolean)
  parts.pop()
  return parts.join('/')
}

function joinTreePath(parentPath: string, childName: string): string {
  return normalizeTreePath(parentPath ? `${parentPath}/${childName}` : childName)
}

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
    return ''
  }
  return node.isDir ? node.path : getParentPath(node.path)
}

function selectedTargetDir(): string {
  const node = selectedTreeNode.value
  if (!node) {
    return ''
  }
  return node.isDir ? node.path : getParentPath(node.path)
}

function findNode(nodes: KnowledgeFileNode[], path: string): KnowledgeFileNode | null {
  for (const node of nodes) {
    if (node.path === path) {
      return node
    }
    const child = node.children ? findNode(node.children, path) : null
    if (child) {
      return child
    }
  }
  return null
}

function flattenVisibleNodes(nodes: KnowledgeFileNode[], expandedPaths: Set<string>): KnowledgeFileNode[] {
  return nodes.flatMap((node) => {
    if (!node.isDir || !expandedPaths.has(node.path)) {
      return [node]
    }
    return [node, ...flattenVisibleNodes(node.children ?? [], expandedPaths)]
  })
}

function rangePathsBetween(anchorPath: string, targetPath: string): string[] {
  const paths = visibleTreeNodes.value.map((node) => node.path)
  const anchorIndex = paths.indexOf(anchorPath)
  const targetIndex = paths.indexOf(targetPath)
  if (anchorIndex < 0 || targetIndex < 0) {
    return [targetPath]
  }
  const start = Math.min(anchorIndex, targetIndex)
  const end = Math.max(anchorIndex, targetIndex)
  return paths.slice(start, end + 1)
}

function insertDraftNode(
  nodes: KnowledgeFileNode[],
  parentPath: string,
  draftNode: KnowledgeFileNode,
): KnowledgeFileNode[] {
  if (!parentPath) {
    return [...nodes, draftNode]
  }
  return nodes.map((node) => {
    if (node.path !== parentPath) {
      return {
        ...node,
        children: node.children ? insertDraftNode(node.children, parentPath, draftNode) : node.children,
      }
    }
    return {
      ...node,
      children: [...(node.children ?? []), draftNode],
    }
  })
}


async function refreshFileTree() {
  actionError.value = ''
  treeVersion.value++
  await workspaceStore.loadKnowledgeTree()
  if (recentMode.value) {
    recentVisitSnapshot.value = workspaceStore.recentFileVisits.map((visit) => ({ ...visit }))
  }
}

function toggleExpandAll() {
  function collectAllDirPaths(nodes: KnowledgeFileNode[]): string[] {
    const result: string[] = []
    for (const node of nodes) {
      if (node.isDir) {
        result.push(node.path)
        if (node.children) {
          result.push(...collectAllDirPaths(node.children))
        }
      }
    }
    return result
  }
  const tree = workspaceStore.tree
  if (!tree.length) return
  const allDirs = collectAllDirPaths(tree)
  const currentExpanded = workspaceStore.expandedPaths
  const allExpanded = allDirs.every((p) => currentExpanded.has(p))
  if (allExpanded) {
    workspaceStore.expandedPaths = new Set()
  } else {
    workspaceStore.expandedPaths = new Set(allDirs)
  }
}

const sortKeyOptions: { value: 'name' | 'mtime' | 'ingested' | 'size'; label: string }[] = [
  { value: 'name', label: '名称排序' },
  { value: 'mtime', label: '修改时间排序' },
  { value: 'ingested', label: '入库时间排序' },
  { value: 'size', label: '大小排序' },
]

const sortDirectionOptions: { value: 'asc' | 'desc'; label: string }[] = [
  { value: 'asc', label: '升序' },
  { value: 'desc', label: '降序' },
]

function selectSortKey(value: 'name' | 'mtime' | 'ingested' | 'size') {
  sortKey.value = value
}

function selectSortDirection(value: 'asc' | 'desc') {
  sortDirection.value = value
  sortMenuOpen.value = false
}

function toggleStatusColumns() {
  const nextVisible = !(settingsStore.showIndexColumn && settingsStore.showGraphColumn)
  settingsStore.setShowIndexColumn(nextVisible)
  settingsStore.setShowGraphColumn(nextVisible)
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

function handleTreeDragEnter() {
  dragging.value = true
}

function handleTreeDragLeave(event: DragEvent) {
  if (event.currentTarget === event.target) {
    dragging.value = false
  }
}

async function handleRootDrop(event: DragEvent) {
  dragging.value = false
  const files = filesFromEvent(event)
  if (files.length > 0) {
    const desktopPaths = desktopPathsFromFiles(files)
    if (desktopPaths.length > 0) {
      await workspaceStore.importExternalPathsToPath(desktopPaths)
      return
    }
    await workspaceStore.importFilesToPath(files)
    return
  }
  const paths = treePathsFromDragEvent(event)
  if (paths.length > 0) {
    await moveDraggedPaths(paths, null)
  }
}

async function handleMultiFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  await workspaceStore.importFilesToPath(Array.from(input.files ?? []))
  input.value = ''
}

async function handleFolderDrop(node: KnowledgeFileNode, files: File[]) {
  dragging.value = false
  const targetDir = node.isDir ? node.path : getParentPath(node.path)
  const desktopPaths = desktopPathsFromFiles(files)
  if (desktopPaths.length > 0) {
    await workspaceStore.importExternalPathsToPath(desktopPaths, targetDir)
    return
  }
  await workspaceStore.importFilesToPath(files, targetDir)
}

async function handleNodeDrop(node: KnowledgeFileNode, paths: string[]) {
  dragging.value = false
  await moveDraggedPaths(paths, node)
}

function handleNodeDragStart(node: KnowledgeFileNode, event: DragEvent) {
  const nodes = workspaceStore.getSelectedTreeNodes(node)
  const paths = nodes.map((item) => item.path)
  event.dataTransfer?.setData('application/x-metaweave-tree-paths', JSON.stringify(paths))
  event.dataTransfer?.setData('text/plain', paths.join('\n'))
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move'
  }
}

async function moveDraggedPaths(paths: string[], targetNode: KnowledgeFileNode | null) {
  const nodes = paths
    .map((path) => findNode(workspaceStore.tree, path))
    .filter((node): node is KnowledgeFileNode => Boolean(node))
  await workspaceStore.moveNodesToDirectory(nodes, targetNode)
}

function treePathsFromDragEvent(event: DragEvent): string[] {
  const rawPaths = event.dataTransfer?.getData('application/x-metaweave-tree-paths') ?? ''
  if (!rawPaths) {
    return []
  }
  try {
    return JSON.parse(rawPaths) as string[]
  } catch {
    return []
  }
}

function handleSelect(node: KnowledgeFileNode, event?: MouseEvent | KeyboardEvent) {
  if (inlineEdit.value?.path === node.path) {
    return
  }
  if (node.isDir) {
    workspaceStore.toggleDirectory(node.path)
  }
  if (event?.shiftKey) {
    workspaceStore.selectTreeNode(node, {
      rangePaths: rangePathsBetween(workspaceStore.selectionAnchorPath || selectedTreePath.value, node.path),
    })
    return
  }
  if (event?.ctrlKey || event?.metaKey) {
    workspaceStore.selectTreeNode(node, { additive: true })
    return
  }
  workspaceStore.selectTreeNode(node)
  if (!node.isDir) {
    workspaceStore.setMainView('editor')
    void workspaceStore.selectFile(node)
  }
}

async function openContextMenu(node: KnowledgeFileNode | null, event: MouseEvent) {
  if (node && !workspaceStore.selectedTreePaths.has(node.path)) {
    workspaceStore.selectTreeNode(node)
  }
  const rawX = event.clientX
  const rawY = event.clientY
  contextMenu.value = {
    open: true,
    x: rawX,
    y: rawY,
    node,
  }
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
    const clampedX = rawX - overflowRight
    const clampedY = rawY - overflowBottom
    contextMenuStyle.value = { left: `${Math.max(0, clampedX)}px`, top: `${Math.max(0, clampedY)}px` }
  }
}

function closeContextMenu() {
  contextMenu.value.open = false
  sortMenuOpen.value = false
}

function isTextInputTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) {
    return false
  }
  return target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)
}

function handleGlobalKeydown(event: KeyboardEvent) {
  if (event.defaultPrevented || isTextInputTarget(event.target)) {
    return
  }
  const key = event.key.toLowerCase()
  const hasCommandModifier = event.ctrlKey || event.metaKey
  if (hasCommandModifier && key === 's') {
    event.preventDefault()
    void workspaceStore.saveActiveFile()
    return
  }
  if (hasCommandModifier && key === 'n') {
    event.preventDefault()
    if (inlineEdit.value || deleteTarget.value) {
      return
    }
    beginCreate(event.shiftKey ? 'folder' : 'file', selectedTargetDir())
    return
  }
  if (hasCommandModifier && key === 'm') {
    event.preventDefault()
    if (inlineEdit.value || deleteTarget.value || !selectedTreeNode.value) {
      return
    }
    beginRename(selectedTreeNode.value)
    return
  }
  if (hasCommandModifier && key === 'c') {
    event.preventDefault()
    if (selectedTreeNode.value) {
      void workspaceStore.copyNode(selectedTreeNode.value)
    }
    return
  }
  if (hasCommandModifier && key === 'x') {
    event.preventDefault()
    if (selectedTreeNode.value) {
      void workspaceStore.cutNode(selectedTreeNode.value)
    }
    return
  }
  if (hasCommandModifier && key === 'v') {
    event.preventDefault()
    void workspaceStore.pasteNode(selectedTreeNode.value)
    return
  }
  if (hasCommandModifier && key === 'd') {
    event.preventDefault()
    if (inlineEdit.value || deleteTarget.value || !selectedTreeNode.value) {
      return
    }
    deleteTarget.value = selectedTreeNode.value
    return
  }
  if (hasCommandModifier && key === 'g') {
    event.preventDefault()
    if (selectedTreeNode.value) {
      void showInGraphFromMenu()
    } else {
      workspaceStore.setMainView('graph')
    }
    return
  }
  if (key === 'escape') {
    closeContextMenu()
    cancelInlineEdit()
    deleteTarget.value = null
  }
}

async function createFileFromMenu() {
  const parentPath = contextTargetDir()
  closeContextMenu()
  leaveRecentMode()
  beginCreate('file', parentPath)
}

async function createFolderFromMenu() {
  const parentPath = contextTargetDir()
  closeContextMenu()
  leaveRecentMode()
  beginCreate('folder', parentPath)
}

async function copyFromMenu() {
  const node = contextMenu.value.node
  closeContextMenu()
  if (node) {
    await workspaceStore.copyNode(node)
  }
}

async function cutFromMenu() {
  const node = contextMenu.value.node
  closeContextMenu()
  if (node) {
    await workspaceStore.cutNode(node)
  }
}

async function copyNameFromMenu() {
  const node = contextMenu.value.node
  closeContextMenu()
  if (!node) {
    return
  }
  await writeClipboardText(node.name)
}

async function copyAbsolutePathFromMenu() {
  const node = contextMenu.value.node
  closeContextMenu()
  if (!node) {
    return
  }
  await writeClipboardText(joinAbsoluteKnowledgePath(node.path))
}

async function copyRelativePathFromMenu() {
  const node = contextMenu.value.node
  closeContextMenu()
  if (!node) {
    return
  }
  await writeClipboardText(node.path)
}

async function writeClipboardText(text: string) {
  if (window.agentEditorDesktop?.writeClipboardText) {
    await window.agentEditorDesktop.writeClipboardText(text)
    return
  }
  await navigator.clipboard?.writeText(text)
}

async function pasteFromMenu() {
  const node = contextMenu.value.node
  closeContextMenu()
  await workspaceStore.pasteNode(node)
}

async function renameFromMenu() {
  const node = contextMenu.value.node
  if (!node) {
    closeContextMenu()
    return
  }
  closeContextMenu()
  leaveRecentMode()
  beginRename(node)
}

function beginRename(node: KnowledgeFileNode) {
  actionError.value = ''
  inlineEdit.value = {
    mode: 'rename',
    kind: node.isDir ? 'folder' : 'file',
    path: node.path,
    parentPath: getParentPath(node.path),
    value: node.name,
    node,
  }
}

async function deleteFromMenu() {
  const node = contextMenu.value.node
  closeContextMenu()
  if (!node) {
    return
  }
  deleteTarget.value = node
}

async function showInFolderFromMenu() {
  const node = contextMenu.value.node
  const absolutePath = node
    ? joinAbsoluteKnowledgePath(node.path)
    : settingsStore.profile.knowledgeDir
  closeContextMenu()
  await window.agentEditorDesktop?.showItemInFolder?.(absolutePath)
}

async function openWithDefaultFromMenu() {
  const node = contextMenu.value.node
  const absolutePath = node
    ? joinAbsoluteKnowledgePath(node.path)
    : settingsStore.profile.knowledgeDir
  closeContextMenu()
  await window.agentEditorDesktop?.openPath?.(absolutePath)
}

function showInGraphFromMenu() {
  closeContextMenu()
  workspaceStore.setMainView('graph')
}

async function extractGraphFromMenu() {
  const node = contextMenu.value.node
  closeContextMenu()
  if (!node) return
  await workspaceStore.extractGraphForNode(node)
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

/** Enters recent mode and captures a stable list ordering for the session. */
function openRecentMode() {
  if (recentMode.value) return
  recentVisitSnapshot.value = workspaceStore.recentFileVisits.map((visit) => ({ ...visit }))
  recentMode.value = true
  sortMenuOpen.value = false
  contextMenu.value.open = false
}

/** Returns to the normal tree and clears transient recent-mode state. */
function leaveRecentMode() {
  recentMode.value = false
  recentSearchQuery.value = ''
  contextMenu.value.open = false
}

async function htmlVisualizeFromMenu() {
  const node = contextMenu.value.node
  closeContextMenu()
  if (!node || node.isDir) {
    return
  }
  await workspaceStore.selectMarkdownHtmlVisualizationDocument(node)
}

async function ingestFromMenu() {
  const node = contextMenu.value.node
  closeContextMenu()
  if (!node) return
  await workspaceStore.ingestFile(node)
}

function ignorePatternForNode(node: KnowledgeFileNode): string {
  const normalizedPath = normalizeTreePath(node.path)
  return node.isDir ? `${normalizedPath}/` : normalizedPath
}

function normalizeIgnorePatternLine(line: string): string {
  return line.replace(/\\/g, '/').trim()
}

function unignorePatternForNode(node: KnowledgeFileNode): string {
  return `!${ignorePatternForNode(node)}`
}

function isSameIgnorePattern(line: string, pattern: string): boolean {
  return normalizeIgnorePatternLine(line) === pattern
}

function isSameUnignorePattern(line: string, pattern: string): boolean {
  return normalizeIgnorePatternLine(line) === `!${pattern}`
}

async function toggleIgnoreFromMenu() {
  const node = contextMenu.value.node
  closeContextMenu()
  if (!node) {
    return
  }
  const pattern = ignorePatternForNode(node)
  const unignorePattern = unignorePatternForNode(node)
  const currentPatterns = settingsStore.profile.knowledgeIgnorePatterns ?? ''
  const currentLines = currentPatterns
    .split(/\r?\n/)
    .map((line) => line.trimEnd())
    .filter((line) => line.trim().length > 0)
  const isCurrentlyIgnored = node.indexStatus === 'ignored'
  const hasExactIgnore = currentLines.some((line) => isSameIgnorePattern(line, pattern))
  const hasExactUnignore = currentLines.some((line) => isSameUnignorePattern(line, pattern))
  let nextLines: string[]
  if (isCurrentlyIgnored) {
    nextLines = hasExactIgnore
      ? currentLines.filter((line) => !isSameIgnorePattern(line, pattern))
      : currentLines
    if (!hasExactIgnore && !hasExactUnignore) {
      nextLines = [...nextLines, unignorePattern]
    }
  } else {
    nextLines = currentLines
      .filter((line) => !isSameUnignorePattern(line, pattern))
    if (!hasExactIgnore) {
      nextLines = [...nextLines, pattern]
    }
  }
  const nextPatterns = nextLines.join('\n')
  actionError.value = ''
  try {
    await settingsStore.saveKnowledgeIngestionSettings({ knowledgeIgnorePatterns: nextPatterns })
    await workspaceStore.loadKnowledgeTree()
    workspaceStore.showToast(`${isCurrentlyIgnored ? 'Unignored' : 'Ignored'} ${node.isDir ? 'folder' : 'file'}: ${node.name}`)
  } catch (error) {
    actionError.value = error instanceof Error ? error.message : 'Failed to save ignore rules.'
  }
}

function beginCreate(kind: 'file' | 'folder', parentPath = '') {
  actionError.value = ''
  if (parentPath) {
    workspaceStore.expandedPaths.add(parentPath)
  }
  const defaultName = kind === 'file' ? 'untitled.md' : 'New Folder'
  inlineEdit.value = {
    mode: 'create',
    kind,
    parentPath,
    path: joinTreePath(parentPath, `__draft_${kind}_${Date.now()}`),
    value: defaultName,
    node: null,
  }
}

function updateInlineValue(value: string) {
  if (!inlineEdit.value) {
    return
  }
  inlineEdit.value.value = value
}

async function commitInlineEdit(value: string) {
  const edit = inlineEdit.value
  const name = normalizeTreePath(value.trim())
  if (!edit) {
    return
  }
  if (!name || name.includes('/')) {
    inlineEdit.value = null
    return
  }
  inlineEdit.value = null
  actionError.value = ''
  try {
    if (edit.mode === 'create') {
      if (edit.kind === 'file') {
        await workspaceStore.createFileAt(edit.parentPath, name)
      } else {
        await workspaceStore.createFolderAt(edit.parentPath, name)
      }
      return
    }
    if (edit.node) {
      await workspaceStore.renameNode(edit.node, name)
    }
  } catch (error) {
    actionError.value = error instanceof Error ? error.message : 'File operation failed.'
  }
}

function cancelInlineEdit() {
  inlineEdit.value = null
}

async function confirmDelete() {
  const node = deleteTarget.value
  if (!node) {
    return
  }
  actionError.value = ''
  try {
    await workspaceStore.deleteNode(node)
    deleteTarget.value = null
  } catch (error) {
    actionError.value = error instanceof Error ? error.message : 'Delete failed.'
  }
}

onMounted(async () => {
  document.addEventListener('click', closeContextMenu)
  window.addEventListener('keydown', handleGlobalKeydown)
  await workspaceStore.loadKnowledgeTree()
  workspaceStore.startFileWatcher()
})

onUnmounted(() => {
  document.removeEventListener('click', closeContextMenu)
  window.removeEventListener('keydown', handleGlobalKeydown)
  workspaceStore.stopFileWatcher()
})
</script>

<template>
  <aside class="file-panel surface-panel" :class="{ dragging, 'recent-mode': recentMode, 'theme-dark': isDark, 'theme-light': !isDark }">
    <div class="panel-header" :class="{ 'recent-header': recentMode }">
      <button
        v-if="recentMode"
        class="header-action"
        type="button"
        title="返回普通文件树"
        aria-label="返回普通文件树"
        @click="leaveRecentMode"
      >
        <ArrowLeft :size="18" />
      </button>
      <button
        v-if="!recentMode"
        class="header-action"
        :class="{ active: settingsStore.showIndexColumn || settingsStore.showGraphColumn }"
        type="button"
        :title="(settingsStore.showIndexColumn || settingsStore.showGraphColumn) ? '隐藏索引与图谱状态' : '显示索引与图谱状态'"
        @click="toggleStatusColumns"
      >
        <ListFilter :size="18" />
      </button>
      <div v-if="!recentMode" class="sort-control" @click.stop>
        <button
          class="header-action"
          :class="{ active: sortMenuOpen }"
          type="button"
          title="排序"
          @click="sortMenuOpen = !sortMenuOpen"
        >
          <ArrowUpDown :size="18" />
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
      <button
        v-if="!recentMode"
        class="header-action"
        type="button"
        title="展开/关闭所有文件夹"
        @click="toggleExpandAll"
      >
        <ChevronsUpDown :size="18" />
      </button>
      <button
        class="header-action"
        :class="{ loading: workspaceStore.treeLoading, 'refresh-btn': true }"
        type="button"
        title="刷新文件树"
        :disabled="workspaceStore.treeLoading"
        @click="refreshFileTree"
      >
        <RefreshCw :size="18" />
      </button>
      <button
        class="header-action"
        :class="{ active: recentMode }"
        type="button"
        title="最近浏览"
        :aria-pressed="recentMode"
        @click="openRecentMode"
      >
        <History :size="18" />
      </button>
      <button v-if="!recentMode" class="header-action" type="button" title="New folder" @click="beginCreate('folder', '')">
        <FolderPlus :size="18" />
      </button>
      <button v-if="!recentMode" class="header-action" type="button" title="New file" @click="beginCreate('file', '')">
        <FilePlus2 :size="18" />
      </button>
      <input
        ref="uploadPicker"
        style="display:none"
        type="file"
        multiple
        @change="handleMultiFileChange"
      />
    </div>

    <label v-if="recentMode" class="recent-search">
      <Search :size="15" aria-hidden="true" />
      <input
        v-model="recentSearchQuery"
        type="search"
        placeholder="按文件名搜索"
        aria-label="按文件名搜索最近浏览"
      />
    </label>

    <RecentFileList
      v-if="recentMode"
      :groups="recentFileGroups"
      :selected-path="workspaceStore.selectedPath"
      :has-history="hasRecentFiles"
      @select="handleSelect"
      @context-menu="openContextMenu"
    />

    <ul
      v-else
      class="tree-root"
      @dragenter.prevent="dragging = true"
      @dragover.prevent="handleTreeDragEnter"
      @dragleave="handleTreeDragLeave"
      @drop.prevent="handleRootDrop"
      @contextmenu.prevent="openContextMenu(null, $event)"
    >
      <TreeNode
        v-for="(node, nodeIndex) in displayTree"
        :key="`${treeVersion}-${node.path}`"
        :node="node"
        :depth="0"
        :stagger-index="nodeIndex"
        :expanded-paths="workspaceStore.expandedPaths"
        :selected-path="selectedTreePath"
        :selected-paths="workspaceStore.selectedTreePaths"
        :dirty-paths="workspaceStore.dirtyFilePaths"
        :editing-path="inlineEdit?.path ?? ''"
        :editing-value="inlineEdit?.value ?? ''"
        @select="handleSelect"
        @drop-files="handleFolderDrop"
        @drop-nodes="handleNodeDrop"
        @node-drag-start="handleNodeDragStart"
        @context-menu="openContextMenu"
        @ingest="workspaceStore.ingestFile"
        @edit-input="updateInlineValue"
        @edit-commit="commitInlineEdit"
        @edit-cancel="cancelInlineEdit"
      />
    </ul>

    <p v-if="actionError" class="action-error">{{ actionError }}</p>

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
      @extract-graph="extractGraphFromMenu"
      @ask-agent="askAgentFromMenu"
      @html-visualize="htmlVisualizeFromMenu"
      @ingest="ingestFromMenu"
      @toggle-ignore="toggleIgnoreFromMenu"
      @delete="deleteFromMenu"
    />

    <div v-if="deleteTarget" class="delete-backdrop" @click.self="deleteTarget = null">
      <section class="delete-dialog" role="dialog" aria-modal="true" aria-labelledby="delete-title">
        <h2 id="delete-title">Confirm delete</h2>
        <p>Delete {{ deleteTarget.name }} from the local knowledge directory.</p>
        <div class="delete-actions">
          <button type="button" @click="deleteTarget = null">取消</button>
          <button type="button" class="danger" @click="confirmDelete">删除</button>
        </div>
      </section>
    </div>
  </aside>
</template>

<style src="./FileTreePanel.css" scoped></style>
