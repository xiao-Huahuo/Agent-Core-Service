<!--
  File tree panel.

  Usage:
  Displays the current knowledge root, recursive file tree, drag-and-drop
  upload target, and watcher/index status placeholders.
-->
<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { FilePlus2, FolderPlus, FolderOpen } from 'lucide-vue-next'

import FileContextMenu from '@/components/editor_workspace/FileContextMenu.vue'
import TreeNode from '@/components/editor_workspace/TreeNode.vue'
import { useSettingsStore } from '@/stores/settings'
import { useWorkspaceStore } from '@/stores/workspace'
import type { KnowledgeFileNode } from '@/types/knowledge'

const settingsStore = useSettingsStore()
const isDark = computed(() => settingsStore.isDark)
const workspaceStore = useWorkspaceStore()
const dragging = ref(false)
const switchingRoot = ref(false)
const savingLibraryName = ref(false)
const rootError = ref('')
const uploadPicker = ref<HTMLInputElement | null>(null)
const libraryNameDraft = ref('')
const contextMenu = ref<{
  open: boolean
  x: number
  y: number
  node: KnowledgeFileNode | null
}>({ open: false, x: 0, y: 0, node: null })
const contextMenuStyle = ref<Record<string, string>>({ left: '0px', top: '0px' })
const contextMenuRef = ref<{ getBoundingClientRect: () => DOMRect } | null>(null)
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
const activeLibraryName = computed(() => {
  return settingsStore.activeKnowledgeLibrary?.name || settingsStore.profile.knowledgeDir
})
const displayTree = computed(() => {
  const edit = inlineEdit.value
  if (!edit || edit.mode !== 'create') {
    return workspaceStore.tree
  }
  const draftNode: KnowledgeFileNode = {
    name: edit.value,
    path: edit.path,
    isDir: edit.kind === 'folder',
    children: edit.kind === 'folder' ? [] : undefined,
    indexStatus: 'dirty',
  }
  return insertDraftNode(workspaceStore.tree, edit.parentPath, draftNode)
})

watch(
  activeLibraryName,
  (name) => {
    libraryNameDraft.value = name
  },
  { immediate: true },
)

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

async function openRootPicker() {
  rootError.value = ''
  actionError.value = ''
  if (window.agentEditorDesktop?.selectDirectory) {
    const selectedDir = await window.agentEditorDesktop.selectDirectory()
    if (!selectedDir) {
      return
    }
    switchingRoot.value = true
    try {
      await settingsStore.switchKnowledgeRoot(selectedDir)
    } catch (error) {
      rootError.value = error instanceof Error ? error.message : 'Failed to switch knowledge root.'
      actionError.value = rootError.value
    } finally {
      await workspaceStore.loadKnowledgeTree()
      workspaceStore.restartFileWatcher()
      switchingRoot.value = false
    }
    return
  }
  rootError.value = 'Switching a local knowledge root requires the Electron directory picker.'
  actionError.value = rootError.value
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

function openMultiFilePicker() {
  uploadPicker.value?.click()
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
  beginCreate('file', parentPath)
}

async function createFolderFromMenu() {
  const parentPath = contextTargetDir()
  closeContextMenu()
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

async function commitLibraryName() {
  const nextName = libraryNameDraft.value.trim()
  if (!nextName || nextName === activeLibraryName.value) {
    libraryNameDraft.value = activeLibraryName.value
    return
  }
  savingLibraryName.value = true
  actionError.value = ''
  try {
    await settingsStore.renameActiveKnowledgeLibrary(nextName)
  } catch (error) {
    actionError.value = error instanceof Error ? error.message : 'Failed to rename knowledge library.'
    libraryNameDraft.value = activeLibraryName.value
  } finally {
    savingLibraryName.value = false
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
  <aside class="file-panel surface-panel" :class="{ dragging, 'theme-dark': isDark, 'theme-light': !isDark }">
    <div class="panel-header">
      <button
        class="root-button"
        type="button"
        :disabled="switchingRoot"
        :title="rootError || 'Switch knowledge root'"
        @click="openRootPicker"
      >
        <FolderOpen :size="18" />
      </button>
      <div class="root-copy">
        <input
          v-model="libraryNameDraft"
          class="library-name-input"
          :disabled="savingLibraryName"
          :title="settingsStore.profile.knowledgeDir"
          spellcheck="false"
          @blur="commitLibraryName"
          @keydown.enter.prevent="commitLibraryName"
          @keydown.escape.prevent="libraryNameDraft = activeLibraryName"
        />
        <span class="root-path" :title="settingsStore.profile.knowledgeDir">
          {{ settingsStore.profile.knowledgeDir }}
        </span>
      </div>
      <button class="header-action" type="button" title="New file" @click="beginCreate('file', '')">
        <FilePlus2 :size="18" />
      </button>
      <button class="header-action" type="button" title="New folder" @click="beginCreate('folder', '')">
        <FolderPlus :size="18" />
      </button>
      <input
        ref="uploadPicker"
        class="root-picker"
        type="file"
        multiple
        @change="handleMultiFileChange"
      />
    </div>

    <ul
      class="tree-root"
      @dragenter.prevent="dragging = true"
      @dragover.prevent="handleTreeDragEnter"
      @dragleave="handleTreeDragLeave"
      @drop.prevent="handleRootDrop"
      @contextmenu.prevent="openContextMenu(null, $event)"
    >
      <TreeNode
        v-for="node in displayTree"
        :key="node.path"
        :node="node"
        :depth="0"
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
      @ask-agent="askAgentFromMenu"
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

<style scoped>
.file-panel {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background:
    linear-gradient(180deg, var(--color-chrome-bg-top), var(--color-chrome-bg-bottom)),
    var(--color-chrome-bg-solid);
  border-left: 0;
}

.file-panel.dragging {
  border-color: var(--color-primary);
}

.panel-header {
  display: flex;
  align-items: center;
  gap: var(--space-6);
  min-height: 44px;
  padding: var(--space-6) var(--space-8);
  border-bottom: 1px solid var(--color-border);
}

.root-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: 28px;
  height: 28px;
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text-secondary);
}

.header-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: 28px;
  height: 28px;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: var(--color-text-secondary);
  transition:
    background var(--transition-fast),
    color var(--transition-fast);
}

.header-action:hover {
  background: var(--color-selection-blue-soft);
  color: var(--color-selection-blue);
}

.root-button:hover {
  background: var(--color-primary-softer);
  color: var(--color-primary);
}

.root-button:disabled {
  cursor: wait;
  opacity: 0.62;
}

.root-copy {
  display: grid;
  flex: 1 1 auto;
  gap: 1px;
  min-width: 0;
}

.library-name-input {
  display: block;
  width: min(150px, 100%);
  min-width: 0;
  height: 18px;
  padding: 0;
  border: 0;
  outline: 0;
  overflow: hidden;
  background: transparent;
  color: var(--color-text);
  font-family: var(--font-ui);
  font-size: 12px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.library-name-input:disabled {
  cursor: wait;
  opacity: 0.62;
}

.root-path {
  display: block;
  overflow: hidden;
  color: var(--color-text-muted);
  font-size: 10px;
  line-height: 1.1;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.root-picker {
  display: none;
}

.spinning {
  animation: root-spin 1s linear infinite;
}

@keyframes root-spin {
  to {
    transform: rotate(360deg);
  }
}

.tree-root {
  flex: 1;
  min-height: 0;
  margin: 0;
  padding: var(--space-8) 0 var(--space-10);
  overflow: auto;
  list-style: none;
  scrollbar-width: thin;
  scrollbar-color: var(--color-border) transparent;
}

.theme-dark .tree-root {
  scrollbar-color: rgba(255, 255, 255, 0.12) transparent;
}

.theme-dark .tree-root::-webkit-scrollbar {
  width: 6px;
}

.theme-dark .tree-root::-webkit-scrollbar-track {
  background: transparent;
}

.theme-dark .tree-root::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.12);
  border-radius: 3px;
}

.theme-dark .tree-root::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.22);
}

.theme-light .tree-root {
  scrollbar-color: rgba(0, 0, 0, 0.15) transparent;
}

.theme-light .tree-root::-webkit-scrollbar {
  width: 6px;
}

.theme-light .tree-root::-webkit-scrollbar-track {
  background: transparent;
}

.theme-light .tree-root::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.15);
  border-radius: 3px;
}

.theme-light .tree-root::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.28);
}

.file-panel.dragging .tree-root {
  background: var(--color-primary-softer);
  outline: 1px dashed rgba(66, 36, 235, 0.5);
  outline-offset: -1px;
}

.context-menu {
  position: fixed;
  z-index: 80;
  display: grid;
  min-width: 210px;
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
}

.context-menu button {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--space-12);
  min-height: 26px;
  padding: 0 var(--space-8);
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text-secondary);
  font-size: 12px;
  text-align: left;
}

.context-menu span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.context-menu kbd {
  color: var(--color-text-muted);
  font-family: var(--font-code);
  font-size: 10px;
}

.context-menu button:hover:not(:disabled) {
  background: var(--color-surface-raised);
  color: var(--color-text);
}

.context-menu button:disabled {
  cursor: default;
  opacity: 0.45;
}

.context-separator {
  margin: var(--space-4) 0;
  border: 0;
  border-top: 1px solid var(--color-border);
}

.context-menu .danger {
  color: var(--color-danger);
}

.action-error {
  margin: 0;
  padding: var(--space-6) var(--space-8);
  border-top: 1px solid var(--color-border);
  color: var(--color-danger);
  font-size: 12px;
}

.delete-backdrop {
  position: fixed;
  inset: 0;
  z-index: 90;
  display: grid;
  place-items: center;
  background: rgba(0, 0, 0, 0.42);
}

.delete-dialog {
  width: min(320px, calc(100vw - 32px));
  padding: var(--space-12);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
}

.delete-dialog h2 {
  margin: 0 0 var(--space-8);
  color: var(--color-text);
  font-size: 14px;
}

.delete-dialog p {
  margin: 0;
  color: var(--color-text-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.delete-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-8);
  margin-top: var(--space-12);
}

.delete-actions button {
  height: 28px;
  padding: 0 var(--space-10);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text-secondary);
}

.delete-actions button:hover {
  background: var(--color-surface-raised);
  color: var(--color-text);
}

.delete-actions .danger {
  border-color: var(--color-danger);
  color: var(--color-danger);
}

</style>
