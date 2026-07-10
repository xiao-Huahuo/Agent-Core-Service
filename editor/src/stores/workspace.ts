/*
 * Knowledge workspace state store.
 *
 * Usage:
 * This store owns the backend file tree, editor tabs, command palette state,
 * and right-side Agent messages.
 */

import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'

import { updateCurrentDocumentContext } from '@/api/agent'
import {
  buildKnowledgeEventsUrl,
  copyKnowledgePath,
  createKnowledgeFile,
  createKnowledgeFolder,
  deleteKnowledgePath,
  listKnowledgeFiles,
  readKnowledgeFile,
  renameKnowledgePath,
  searchKnowledge,
  uploadKnowledgeFile,
  writeKnowledgeFile,
} from '@/api/knowledge'
import { rebuildKnowledgeRoot } from '@/api/settings'
import { useSettingsStore } from '@/stores/settings'
import type {
  ChatMessage,
  CommandAction,
  EditorTab,
  EditorViewMode,
  KnowledgeFileNode,
  SearchResults,
  WorkspaceMainView,
} from '@/types/knowledge'

function createId(prefix: string): string {
  return `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`
}

function flattenNodes(nodes: KnowledgeFileNode[]): KnowledgeFileNode[] {
  return nodes.flatMap((node) => [node, ...(node.children ? flattenNodes(node.children) : [])])
}

function collectDirectoryPaths(nodes: KnowledgeFileNode[]): string[] {
  return nodes.flatMap((node) => {
    if (!node.isDir) {
      return []
    }
    return [node.path, ...collectDirectoryPaths(node.children ?? [])]
  })
}

function formatMtime(date = new Date()): string {
  const pad = (value: number) => value.toString().padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function normalizeTreePath(path: string): string {
  return path.replace(/\\/g, '/').replace(/^\/+|\/+$/g, '')
}

function joinTreePath(parentPath: string, childName: string): string {
  return normalizeTreePath(parentPath ? `${parentPath}/${childName}` : childName)
}

function getParentPath(path: string): string {
  const parts = normalizeTreePath(path).split('/').filter(Boolean)
  parts.pop()
  return parts.join('/')
}

function getBaseName(path: string): string {
  const parts = normalizeTreePath(path).split('/').filter(Boolean)
  return parts[parts.length - 1] ?? ''
}

function buildAbsoluteKnowledgePath(knowledgeDir: string, relativePath: string): string {
  const root = knowledgeDir.replace(/[\\/]+$/g, '')
  const child = normalizeTreePath(relativePath)
  if (!child) {
    return root
  }
  return `${root}\\${child.replace(/\//g, '\\')}`
}

function splitExtension(name: string): { stem: string; extension: string } {
  const dotIndex = name.lastIndexOf('.')
  if (dotIndex <= 0) {
    return { stem: name, extension: '' }
  }
  return { stem: name.slice(0, dotIndex), extension: name.slice(dotIndex) }
}

function childDirectoryFor(node?: KnowledgeFileNode | null): string {
  if (!node) {
    return ''
  }
  return node.isDir ? node.path : getParentPath(node.path)
}

function getRelativeFilePath(file: File): string {
  return normalizeTreePath(file.webkitRelativePath || file.name)
}

function stripRootFolder(path: string): string {
  const parts = normalizeTreePath(path).split('/').filter(Boolean)
  return parts.length > 1 ? parts.slice(1).join('/') : parts.join('/')
}

function createImportedFileNode(path: string, file: File): KnowledgeFileNode {
  const parts = normalizeTreePath(path).split('/').filter(Boolean)
  return {
    name: parts[parts.length - 1] ?? file.name,
    path,
    isDir: false,
    size: file.size,
    mtime: formatMtime(new Date(file.lastModified || Date.now())),
    indexStatus: 'indexing',
  }
}

function upsertFileNode(
  nodes: KnowledgeFileNode[],
  relativePath: string,
  file: File,
  expanded: Set<string>,
) {
  const parts = normalizeTreePath(relativePath).split('/').filter(Boolean)
  if (parts.length === 0) {
    return
  }
  let currentNodes = nodes
  let currentPath = ''
  for (const part of parts.slice(0, -1)) {
    currentPath = joinTreePath(currentPath, part)
    let dirNode = currentNodes.find((node) => node.isDir && node.name === part)
    if (!dirNode) {
      dirNode = {
        name: part,
        path: currentPath,
        isDir: true,
        indexStatus: 'indexing',
        children: [],
      }
      currentNodes.push(dirNode)
    }
    dirNode.indexStatus = 'indexing'
    dirNode.children ??= []
    expanded.add(dirNode.path)
    currentNodes = dirNode.children
  }

  const filePath = normalizeTreePath(relativePath)
  const importedNode = createImportedFileNode(filePath, file)
  const existingIndex = currentNodes.findIndex((node) => node.path === importedNode.path)
  if (existingIndex >= 0) {
    currentNodes.splice(existingIndex, 1, importedNode)
    return
  }
  currentNodes.push(importedNode)
}

function isLikelyTextFile(file: File): boolean {
  if (file.type.startsWith('text/')) {
    return true
  }
  return /\.(c|cpp|css|go|html|java|js|json|jsx|md|py|rs|ts|tsx|txt|vue|xml|yaml|yml)$/i.test(file.name)
}

async function readFilePreview(file: File): Promise<string> {
  if (!isLikelyTextFile(file)) {
    return `# ${file.name}\n\nBinary file placeholder. Backend import and indexing will handle the original file.`
  }
  try {
    return await file.text()
  } catch {
    return `# ${file.name}\n\nUnable to preview this file in the browser shell.`
  }
}

export const useWorkspaceStore = defineStore('workspace', () => {
  /** Recursive knowledge file tree loaded from the backend. */
  const tree = ref<KnowledgeFileNode[]>([])

  /** Expanded directory paths. */
  const expandedPaths = ref<Set<string>>(new Set())

  /** Current file path selected in the editor. */
  const selectedPath = ref('')

  /** Current file or directory path highlighted in the tree. */
  const selectedTreePath = ref('')

  /** Active editor mode. */
  const editorMode = ref<EditorViewMode>('edit')

  /** Active center workspace view. */
  const mainView = ref<WorkspaceMainView>('editor')

  /** Open file tabs. */
  const openTabs = ref<EditorTab[]>([])

  /** Local file content cache. */
  const contentByPath = ref<Record<string, string>>({})

  /** Command palette visibility. */
  const commandPaletteOpen = ref(false)

  /** Agent panel message history. */
  const chatMessages = ref<ChatMessage[]>([
    {
      id: 'system_intro',
      role: 'system',
      content: 'Agent panel is ready. Backend streaming will be connected later.',
    },
  ])

  /** Active backend file-event stream. */
  const fileEvents = ref<EventSource | null>(null)

  /** File tree loading state. */
  const treeLoading = ref(false)

  /** Tracks how many pending tree_dirty events should suppress tab-dirty marking. */
  const ignoreNextTreeEvent = ref(0)

  /** Whether the refresh/indexing operation is in progress. */
  const refreshing = ref(false)

  /** Toast notification message (empty = hidden). */
  const toastMessage = ref('')
  const toastVisible = ref(false)
  let toastTimer: ReturnType<typeof setTimeout> | null = null

  /** File-tree multi-selection set used by click, Shift-click, and Ctrl-click. */
  const selectedTreePaths = ref<Set<string>>(new Set())

  /** Last focused tree path used as the range anchor for Shift-click. */
  const selectionAnchorPath = ref('')

  /** Pending copy/cut operation for context-menu paste and keyboard paste. */
  const fileClipboard = ref<{ mode: 'copy' | 'cut'; nodes: KnowledgeFileNode[] } | null>(null)

  /** Whether the Agent sidebar is visible. Shared so child components can open it. */
  const agentSidebarOpen = ref(true)

  /** 由子组件设置的待发送 Agent 消息,AgentPanel 消费后清空。 */
  const pendingAgentPrompt = ref('')

  /** 用户引用的文本,AgentPanel 消费后清空,由 SelectionToolbar 设置。 */
  const pendingAgentReference = ref('')

  /** Search palette state. */
  const searchQuery = ref('')
  const searchResults = ref<SearchResults | null>(null)
  const searchOpen = ref(false)
  const searching = ref(false)
  const fulltextEnabled = ref(true)
  const semanticEnabled = ref(false)
  const searchUnified = ref(false)

  /** Search history (persisted to localStorage). */
  const SEARCH_HISTORY_KEY = 'metweave_search_history'
  const searchHistory = ref<string[]>([])
  try {
    const raw = localStorage.getItem(SEARCH_HISTORY_KEY)
    if (raw) searchHistory.value = JSON.parse(raw) as string[]
  } catch { /* ignore corrupt data */ }

  function addSearchHistory(query: string) {
    const trimmed = query.trim()
    if (!trimmed) return
    searchHistory.value = [trimmed, ...searchHistory.value.filter((q) => q !== trimmed)].slice(0, 20)
    try { localStorage.setItem(SEARCH_HISTORY_KEY, JSON.stringify(searchHistory.value)) } catch { /* ignore */ }
  }

  function clearSearchHistory() {
    searchHistory.value = []
    try { localStorage.removeItem(SEARCH_HISTORY_KEY) } catch { /* ignore */ }
  }

  let currentDocumentContextTimer: number | null = null

  const flatNodes = computed(() => flattenNodes(tree.value))

  const selectedNode = computed(() => flatNodes.value.find((node) => node.path === selectedPath.value))

  const activeContent = computed(() => contentByPath.value[selectedPath.value] ?? '')

  const activeTab = computed(() => openTabs.value.find((tab) => tab.path === selectedPath.value))

  const dirtyFilePaths = computed(() => new Set(openTabs.value.filter((tab) => tab.dirty).map((tab) => tab.path)))

  const hasDirtyTabs = computed(() => openTabs.value.some((tab) => tab.dirty))

  function activeDocumentContextNode(): KnowledgeFileNode | null {
    if (!selectedPath.value) {
      return null
    }
    return flatNodes.value.find((node) => node.path === selectedPath.value) ?? null
  }

  function syncCurrentDocumentContext() {
    if (currentDocumentContextTimer !== null) {
      window.clearTimeout(currentDocumentContextTimer)
      currentDocumentContextTimer = null
    }
    const settingsStore = useSettingsStore()
    if (!settingsStore.profile.userId) {
      return
    }
    const node = activeDocumentContextNode()
    const tab = activeTab.value
    const library = settingsStore.activeKnowledgeLibrary
    void updateCurrentDocumentContext({
      user_id: settingsStore.profile.userId,
      path: selectedPath.value,
      name: node?.name ?? tab?.title ?? getBaseName(selectedPath.value),
      knowledge_dir: settingsStore.profile.knowledgeDir,
      library_id: library?.libraryId ?? settingsStore.profile.activeLibraryId,
      library_name: library?.name ?? '',
      size: node?.size,
      mtime: node?.mtime,
      dirty: Boolean(tab?.dirty),
      open_tab_count: openTabs.value.length,
    }).catch(() => {
      // Current-document context is a best-effort UI hint for Agent tools.
    })
  }

  function queueCurrentDocumentContextSync() {
    if (currentDocumentContextTimer !== null) {
      window.clearTimeout(currentDocumentContextTimer)
    }
    currentDocumentContextTimer = window.setTimeout(() => {
      currentDocumentContextTimer = null
      syncCurrentDocumentContext()
    }, 350)
  }

  const commands = computed<CommandAction[]>(() => [
    {
      id: 'toggle-theme',
      label: 'Toggle theme',
      shortcut: 'T',
      description: 'Switch between dark and light editor surfaces.',
    },
    {
      id: 'run-index',
      label: 'Run indexing',
      shortcut: 'I',
      description: 'Queue a mock re-index job for the current knowledge root.',
    },
    {
      id: 'open-settings',
      label: 'Open settings',
      shortcut: ',',
      description: 'Adjust knowledge root and watcher settings.',
    },
    {
      id: 'open-graph',
      label: 'Open graph',
      shortcut: 'G',
      description: 'Preview the future knowledge graph page.',
    },
  ])

  function toggleDirectory(path: string) {
    if (expandedPaths.value.has(path)) {
      expandedPaths.value.delete(path)
      return
    }
    expandedPaths.value.add(path)
  }

  function setTreeSelection(paths: string[], anchorPath = paths[paths.length - 1] ?? '') {
    selectedTreePaths.value = new Set(paths.map(normalizeTreePath).filter(Boolean))
    selectionAnchorPath.value = anchorPath
  }

  function clearTreeSelection() {
    selectedTreePaths.value = new Set()
    selectionAnchorPath.value = ''
  }

  function selectTreeNode(node: KnowledgeFileNode, options: { rangePaths?: string[]; additive?: boolean } = {}) {
    const path = normalizeTreePath(node.path)
    if (options.rangePaths && options.rangePaths.length > 0) {
      setTreeSelection(options.rangePaths, selectionAnchorPath.value || path)
      selectedTreePath.value = path
      return
    }
    if (options.additive) {
      const next = new Set(selectedTreePaths.value)
      if (next.has(path)) {
        next.delete(path)
      } else {
        next.add(path)
      }
      selectedTreePaths.value = next
      selectionAnchorPath.value = path
      selectedTreePath.value = path
      return
    }
    setTreeSelection([path], path)
    selectedTreePath.value = path
  }

  function getSelectedTreeNodes(fallbackNode?: KnowledgeFileNode | null): KnowledgeFileNode[] {
    const selected = flatNodes.value.filter((node) => selectedTreePaths.value.has(node.path))
    if (fallbackNode && selected.some((node) => node.path === fallbackNode.path)) {
      return selected
    }
    if (fallbackNode) {
      return [fallbackNode]
    }
    return selected
  }

  function pruneNestedNodes(nodes: KnowledgeFileNode[]): KnowledgeFileNode[] {
    return nodes.filter((node) => !nodes.some((candidate) => candidate.path !== node.path && isSameOrChildPath(node.path, candidate.path)))
  }

  async function selectFile(node: KnowledgeFileNode) {
    selectedTreePath.value = node.path
    if (node.isDir) {
      toggleDirectory(node.path)
      return
    }
    selectedPath.value = node.path
    if (!openTabs.value.some((tab) => tab.path === node.path)) {
      openTabs.value.push({ path: node.path, title: node.name, dirty: false, mtime: node.mtime })
    }
    if (contentByPath.value[node.path] === undefined) {
      await loadFileContent(node.path)
    }
    queueCurrentDocumentContextSync()
  }

  function activateTab(path: string) {
    selectedPath.value = path
    selectedTreePath.value = path
    syncCurrentDocumentContext()
  }

  function closeTab(path: string) {
    const nextTabs = openTabs.value.filter((tab) => tab.path !== path)
    openTabs.value = nextTabs
    if (selectedPath.value !== path) {
      return
    }
    const fallback = nextTabs[0]
    selectedPath.value = fallback?.path ?? ''
    if (selectedTreePath.value === path) {
      selectedTreePath.value = fallback?.path ?? ''
    }
    syncCurrentDocumentContext()
  }

  function setEditorMode(mode: EditorViewMode) {
    editorMode.value = mode
  }

  function setMainView(view: WorkspaceMainView) {
    mainView.value = view
  }

  function updateActiveContent(content: string) {
    if (!selectedPath.value) {
      return
    }
    contentByPath.value[selectedPath.value] = content
    const tab = openTabs.value.find((item) => item.path === selectedPath.value)
    if (tab) {
      tab.dirty = true
    }
    queueCurrentDocumentContextSync()
  }

  async function saveActiveFile() {
    const tab = activeTab.value
    if (!tab || !selectedPath.value) {
      return
    }
    await saveFileByPath(tab.path)
  }

  async function saveFileByPath(path: string) {
    const tab = openTabs.value.find((item) => item.path === path)
    if (!tab) {
      return
    }
    const settingsStore = useSettingsStore()
    ignoreNextTreeEvent.value += 3
    await writeKnowledgeFile(settingsStore.profile.userId, path, contentByPath.value[path] ?? '')
    tab.dirty = false
    await loadKnowledgeTree()
    const savedNode = flatNodes.value.find((n) => n.path === path)
    if (savedNode?.mtime) tab.mtime = savedNode.mtime
    if (path === selectedPath.value) {
      syncCurrentDocumentContext()
    }
  }

  async function saveAllDirtyFiles() {
    const dirtyPaths = openTabs.value.filter((tab) => tab.dirty).map((tab) => tab.path)
    for (const path of dirtyPaths) {
      await saveFileByPath(path)
    }
  }

  async function confirmSaveDirtyBeforeExit() {
    if (!hasDirtyTabs.value) {
      return true
    }
    const shouldSave = window.confirm('还有未保存的文件。是否保存所有文件后退出？')
    if (!shouldSave) {
      return false
    }
    await saveAllDirtyFiles()
    return true
  }

  async function importFilesToPath(files: File[], targetDirPath = '') {
    const targetPath = normalizeTreePath(targetDirPath)
    const importedFiles = files.filter((file) => file.name)
    if (importedFiles.length === 0) {
      return
    }
    const settingsStore = useSettingsStore()
    ignoreNextTreeEvent.value += 3
    const uploaded: string[] = []
    const failed: string[] = []
    for (const file of importedFiles) {
      try {
        await uploadKnowledgeFile(settingsStore.profile.userId, file, targetPath)
        uploaded.push(file.name)
      } catch {
        failed.push(file.name)
      }
    }
    await loadKnowledgeTree()
    selectedTreePath.value = targetPath
    syncCurrentDocumentContext()
    if (failed.length === 0 && uploaded.length > 0) {
      showToast(`Imported ${uploaded.length} file${uploaded.length > 1 ? 's' : ''} and re-indexed`)
    } else if (failed.length > 0 && uploaded.length > 0) {
      showToast(`Imported ${uploaded.length}, skipped ${failed.length} file${failed.length > 1 ? 's' : ''}`)
    } else if (failed.length > 0) {
      showToast(`Import failed for ${failed.length} file${failed.length > 1 ? 's' : ''}`)
    }
  }

  async function scanKnowledgeRoot(files: File[]) {
    const nextTree: KnowledgeFileNode[] = []
    const nextContent: Record<string, string> = {}
    const nextExpandedPaths = new Set<string>()
    for (const file of files.filter((item) => item.name)) {
      const relativePath = stripRootFolder(getRelativeFilePath(file))
      if (!relativePath) {
        continue
      }
      upsertFileNode(nextTree, relativePath, file, nextExpandedPaths)
      nextContent[relativePath] = await readFilePreview(file)
    }
    tree.value = nextTree
    expandedPaths.value = nextExpandedPaths
    contentByPath.value = nextContent
    selectedPath.value = ''
    selectedTreePath.value = ''
    openTabs.value = []
    syncCurrentDocumentContext()
  }

  function openCommandPalette() {
    commandPaletteOpen.value = true
  }

  function closeCommandPalette() {
    commandPaletteOpen.value = false
  }

  function openSearch() {
    searchOpen.value = true
    searchQuery.value = ''
    searchResults.value = null
  }

  function closeSearch() {
    searchOpen.value = false
    searchQuery.value = ''
    searchResults.value = null
  }

  async function performSearch(query: string) {
    const trimmed = query.trim()
    if (!trimmed) {
      searchResults.value = null
      return
    }
    addSearchHistory(trimmed)
    searching.value = true
    try {
      const settingsStore = useSettingsStore()
      searchResults.value = await searchKnowledge(
        settingsStore.profile.userId,
        trimmed,
        fulltextEnabled.value,
        semanticEnabled.value,
      )
    } catch {
      searchResults.value = null
    } finally {
      searching.value = false
    }
  }

  let _searchTimer: ReturnType<typeof setTimeout> | null = null
  watch(searchQuery, (value) => {
    if (_searchTimer !== null) {
      clearTimeout(_searchTimer)
    }
    _searchTimer = setTimeout(() => {
      _searchTimer = null
      performSearch(value)
    }, 300)
  })

  function askAgent(content: string) {
    const trimmed = content.trim()
    if (!trimmed) {
      return
    }
    chatMessages.value.push({
      id: createId('user'),
      role: 'user',
      content: trimmed,
      sourcePath: selectedPath.value,
    })
    chatMessages.value.push({
      id: createId('assistant'),
      role: 'assistant',
      content: `Mock response scoped to ${selectedPath.value || 'the whole knowledge base'}. Backend Agent streaming will replace this placeholder.`,
      sourcePath: selectedPath.value,
    })
  }

  async function markIndexing() {
    if (refreshing.value) return
    refreshing.value = true
    tree.value = tree.value.map((node) => ({ ...node, indexStatus: 'indexing' }))
    const settingsStore = useSettingsStore()
    if (!settingsStore.profile.userId) {
      refreshing.value = false
      return
    }
    try {
      await loadKnowledgeTree()
      if (activeTab.value) {
        const tab = activeTab.value
        const response = await readKnowledgeFile(settingsStore.profile.userId, tab.path)
        contentByPath.value = { ...contentByPath.value, [tab.path]: response.content }
        tab.dirty = false
        tab.mtime = response.mtime
      }
      const result = await rebuildKnowledgeRoot(settingsStore.profile.userId)
      showToast(`Refresh complete — ${result.files_ingested} files re-indexed`)
    } catch {
      showToast('Refresh failed — check your connection')
    } finally {
      refreshing.value = false
    }
  }

  function showToast(message: string, duration = 3500) {
    toastMessage.value = message
    toastVisible.value = true
    if (toastTimer !== null) clearTimeout(toastTimer)
    toastTimer = setTimeout(() => {
      toastVisible.value = false
      toastTimer = null
    }, duration)
  }

  async function createFileAt(parentDirPath = '', preferredName = 'untitled.md') {
    const settingsStore = useSettingsStore()
    const targetPath = uniquePathInDirectory(parentDirPath, preferredName)
    ignoreNextTreeEvent.value += 1
    await createKnowledgeFile(settingsStore.profile.userId, targetPath, '')
    contentByPath.value = { ...contentByPath.value, [targetPath]: '' }
    await loadKnowledgeTree()
    await selectFile({ name: getBaseName(targetPath), path: targetPath, isDir: false })
  }

  async function createFolderAt(parentDirPath = '', preferredName = 'New Folder') {
    const settingsStore = useSettingsStore()
    const targetPath = uniquePathInDirectory(parentDirPath, preferredName)
    ignoreNextTreeEvent.value += 1
    await createKnowledgeFolder(settingsStore.profile.userId, targetPath)
    await loadKnowledgeTree()
    expandedPaths.value.add(targetPath)
    selectedTreePath.value = targetPath
  }

  async function copyNode(node: KnowledgeFileNode) {
    const nodes = pruneNestedNodes(getSelectedTreeNodes(node))
    fileClipboard.value = { mode: 'copy', nodes }
    await copyNodesToSystemClipboard(nodes, 'copy')
  }

  async function cutNode(node: KnowledgeFileNode) {
    const nodes = pruneNestedNodes(getSelectedTreeNodes(node))
    fileClipboard.value = { mode: 'cut', nodes }
    await copyNodesToSystemClipboard(nodes, 'cut')
  }

  async function copyNodesToSystemClipboard(nodes: KnowledgeFileNode[], mode: 'copy' | 'cut') {
    const settingsStore = useSettingsStore()
    const absolutePaths = nodes.map((node) => buildAbsoluteKnowledgePath(settingsStore.profile.knowledgeDir, node.path))
    if (window.agentEditorDesktop?.copyFilePaths) {
      await window.agentEditorDesktop.copyFilePaths(absolutePaths, mode)
      return
    }
    await navigator.clipboard?.writeText(absolutePaths.join('\n'))
  }

  async function pasteNode(targetNode?: KnowledgeFileNode | null) {
    const pending = fileClipboard.value
    if (!pending || pending.nodes.length === 0) {
      await pasteExternalClipboardPaths(targetNode)
      return
    }
    const settingsStore = useSettingsStore()
    const targetDir = childDirectoryFor(targetNode)
    const reservedPaths = new Set(flatNodes.value.map((node) => node.path))
    let lastTargetPath = ''
    ignoreNextTreeEvent.value += pending.nodes.length
    for (const node of pending.nodes) {
      if (pending.mode === 'cut' && targetDir === getParentPath(node.path)) {
        continue
      }
      const targetPath = uniquePathInDirectoryWithReserved(targetDir, node.name, reservedPaths)
      reservedPaths.add(targetPath)
      if (pending.mode === 'copy') {
        await copyKnowledgePath(settingsStore.profile.userId, node.path, targetPath)
      } else {
        await renameKnowledgePath(settingsStore.profile.userId, node.path, targetPath)
        rewriteOpenPaths(node.path, targetPath)
      }
      lastTargetPath = targetPath
    }
    if (pending.mode === 'cut') {
      fileClipboard.value = null
    }
    await loadKnowledgeTree()
    if (lastTargetPath) {
      setTreeSelection([lastTargetPath], lastTargetPath)
      selectedTreePath.value = lastTargetPath
    }
    syncCurrentDocumentContext()
  }

  async function moveNodesToDirectory(nodes: KnowledgeFileNode[], targetNode?: KnowledgeFileNode | null) {
    const targetDir = childDirectoryFor(targetNode)
    const movableNodes = pruneNestedNodes(nodes).filter((node) => {
      if (targetDir === getParentPath(node.path)) {
        return false
      }
      return !node.isDir || !isSameOrChildPath(targetDir, node.path)
    })
    if (movableNodes.length === 0) {
      return
    }
    const settingsStore = useSettingsStore()
    const reservedPaths = new Set(flatNodes.value.map((node) => node.path))
    const movedPaths: string[] = []
    ignoreNextTreeEvent.value += movableNodes.length
    for (const node of movableNodes) {
      const targetPath = uniquePathInDirectoryWithReserved(targetDir, node.name, reservedPaths)
      reservedPaths.add(targetPath)
      await renameKnowledgePath(settingsStore.profile.userId, node.path, targetPath)
      rewriteOpenPaths(node.path, targetPath)
      movedPaths.push(targetPath)
    }
    await loadKnowledgeTree()
    setTreeSelection(movedPaths, movedPaths[movedPaths.length - 1] ?? '')
    syncCurrentDocumentContext()
  }

  async function pasteExternalClipboardPaths(targetNode?: KnowledgeFileNode | null) {
    const desktop = window.agentEditorDesktop
    if (!desktop?.copyExternalPathsIntoDirectory) {
      return
    }
    const clipboardFiles = desktop.readClipboardFiles
      ? await desktop.readClipboardFiles()
      : { mode: 'copy' as const, paths: await desktop.readClipboardFilePaths?.() ?? [] }
    const sourcePaths = clipboardFiles.paths
    if (sourcePaths.length === 0) {
      return
    }
    const targetDir = childDirectoryFor(targetNode)
    const targetAbsoluteDir = buildAbsoluteKnowledgePath(useSettingsStore().profile.knowledgeDir, targetDir)
    ignoreNextTreeEvent.value += sourcePaths.length
    const result = await desktop.copyExternalPathsIntoDirectory(sourcePaths, targetAbsoluteDir, clipboardFiles.mode)
    await loadKnowledgeTree()
    if (result.paths.length > 0) {
      const root = useSettingsStore().profile.knowledgeDir.replace(/[\\/]+$/g, '')
      const relativePaths = result.paths.map((path) => normalizeTreePath(path.replace(root, '')))
      setTreeSelection(relativePaths, relativePaths[relativePaths.length - 1] ?? '')
    }
    syncCurrentDocumentContext()
  }

  async function renameNode(node: KnowledgeFileNode, nextName: string) {
    const normalizedName = normalizeTreePath(nextName)
    if (!normalizedName || normalizedName.includes('/')) {
      return
    }
    const targetPath = joinTreePath(getParentPath(node.path), normalizedName)
    if (targetPath === node.path) {
      return
    }
    const settingsStore = useSettingsStore()
    ignoreNextTreeEvent.value += 1
    await renameKnowledgePath(settingsStore.profile.userId, node.path, targetPath)
    rewriteOpenPaths(node.path, targetPath)
    await loadKnowledgeTree()
    selectedTreePath.value = targetPath
    syncCurrentDocumentContext()
  }

  async function deleteNode(node: KnowledgeFileNode) {
    const settingsStore = useSettingsStore()
    ignoreNextTreeEvent.value += 1
    await deleteKnowledgePath(settingsStore.profile.userId, node.path)
    openTabs.value = openTabs.value.filter((tab) => !isSameOrChildPath(tab.path, node.path))
    Object.keys(contentByPath.value).forEach((path) => {
      if (isSameOrChildPath(path, node.path)) {
        delete contentByPath.value[path]
      }
    })
    if (isSameOrChildPath(selectedPath.value, node.path)) {
      selectedPath.value = openTabs.value[0]?.path ?? ''
    }
    selectedTreePath.value = selectedPath.value
    await loadKnowledgeTree()
    syncCurrentDocumentContext()
  }

  async function loadKnowledgeTree() {
    const settingsStore = useSettingsStore()
    if (!settingsStore.profile.userId) {
      return
    }
    treeLoading.value = true
    try {
      const response = await listKnowledgeFiles(settingsStore.profile.userId)
      tree.value = response.tree
      expandedPaths.value = new Set(collectDirectoryPaths(response.tree))
      if (selectedPath.value && !flatNodes.value.some((node) => node.path === selectedPath.value)) {
        selectedPath.value = ''
        selectedTreePath.value = ''
        openTabs.value = []
      }
      syncCurrentDocumentContext()
    } finally {
      treeLoading.value = false
    }
  }

  async function loadFileContent(path: string) {
    const settingsStore = useSettingsStore()
    const response = await readKnowledgeFile(settingsStore.profile.userId, path)
    contentByPath.value = { ...contentByPath.value, [path]: response.content }
    const tab = openTabs.value.find((t) => t.path === path)
    if (tab) tab.mtime = response.mtime
    syncCurrentDocumentContext()
  }

  function startFileWatcher() {
    const settingsStore = useSettingsStore()
    if (!settingsStore.profile.userId || fileEvents.value || typeof EventSource === 'undefined') {
      return
    }
    const eventSource = new EventSource(buildKnowledgeEventsUrl(settingsStore.profile.userId))
    eventSource.addEventListener('tree_dirty', async () => {
      await loadKnowledgeTree()
      if (ignoreNextTreeEvent.value > 0) {
        ignoreNextTreeEvent.value -= 1
        return
      }
      markOpenTabsDirty()
    })
    eventSource.onerror = () => {
      eventSource.close()
      fileEvents.value = null
    }
    fileEvents.value = eventSource
  }

  function stopFileWatcher() {
    fileEvents.value?.close()
    fileEvents.value = null
  }

  function restartFileWatcher() {
    stopFileWatcher()
    startFileWatcher()
  }

  function markOpenTabsDirty() {
    const nodeByPath = new Map(flatNodes.value.map((n) => [n.path, n]))
    openTabs.value = openTabs.value.map((tab) => {
      const node = nodeByPath.get(tab.path)
      if (!node || !tab.mtime) return { ...tab, dirty: true }
      const changed = node.mtime !== tab.mtime
      return { ...tab, dirty: changed, mtime: changed ? tab.mtime : node.mtime }
    })
  }

  function uniquePathInDirectory(parentDirPath: string, preferredName: string): string {
    const existingPaths = new Set(flatNodes.value.map((node) => node.path))
    return uniquePathInDirectoryWithReserved(parentDirPath, preferredName, existingPaths)
  }

  function uniquePathInDirectoryWithReserved(
    parentDirPath: string,
    preferredName: string,
    existingPaths: Set<string>,
  ): string {
    const safeName = normalizeTreePath(preferredName).split('/').filter(Boolean).join('-') || 'untitled.md'
    const firstPath = joinTreePath(parentDirPath, safeName)
    if (!existingPaths.has(firstPath)) {
      return firstPath
    }
    const { stem, extension } = splitExtension(safeName)
    for (let index = 2; index < 1000; index += 1) {
      const candidate = joinTreePath(parentDirPath, `${stem} ${index}${extension}`)
      if (!existingPaths.has(candidate)) {
        return candidate
      }
    }
    return joinTreePath(parentDirPath, `${stem} ${Date.now()}${extension}`)
  }

  function rewriteOpenPaths(sourcePath: string, targetPath: string) {
    openTabs.value = openTabs.value.map((tab) => {
      if (!isSameOrChildPath(tab.path, sourcePath)) {
        return tab
      }
      const nextPath = tab.path.replace(sourcePath, targetPath)
      return { ...tab, path: nextPath, title: getBaseName(nextPath) }
    })
    Object.entries(contentByPath.value).forEach(([path, content]) => {
      if (!isSameOrChildPath(path, sourcePath)) {
        return
      }
      const nextPath = path.replace(sourcePath, targetPath)
      delete contentByPath.value[path]
      contentByPath.value[nextPath] = content
    })
    if (isSameOrChildPath(selectedPath.value, sourcePath)) {
      selectedPath.value = selectedPath.value.replace(sourcePath, targetPath)
    }
  }

  function isSameOrChildPath(path: string, parentPath: string): boolean {
    return path === parentPath || path.startsWith(`${parentPath}/`)
  }

  return {
    tree,
    expandedPaths,
    selectedPath,
    selectedTreePath,
    selectedTreePaths,
    selectionAnchorPath,
    selectedNode,
    mainView,
    editorMode,
    openTabs,
    activeContent,
    activeTab,
    dirtyFilePaths,
    hasDirtyTabs,
    commandPaletteOpen,
    chatMessages,
    commands,
    treeLoading,
    fileClipboard,
    refreshing,
    toastMessage,
    toastVisible,
    showToast,
    agentSidebarOpen,
    pendingAgentPrompt,
    pendingAgentReference,
    toggleDirectory,
    selectTreeNode,
    setTreeSelection,
    clearTreeSelection,
    getSelectedTreeNodes,
    selectFile,
    activateTab,
    closeTab,
    setEditorMode,
    setMainView,
    updateActiveContent,
    saveActiveFile,
    saveAllDirtyFiles,
    confirmSaveDirtyBeforeExit,
    importFilesToPath,
    scanKnowledgeRoot,
    openCommandPalette,
    closeCommandPalette,
    flatNodes,
    searchQuery,
    searchResults,
    searchOpen,
    searching,
    fulltextEnabled,
    semanticEnabled,
    searchUnified,
    openSearch,
    closeSearch,
    searchHistory,
    addSearchHistory,
    clearSearchHistory,
    performSearch,
    askAgent,
    syncCurrentDocumentContext,
    markIndexing,
    createFileAt,
    createFolderAt,
    copyNode,
    cutNode,
    pasteNode,
    moveNodesToDirectory,
    renameNode,
    deleteNode,
    loadKnowledgeTree,
    startFileWatcher,
    stopFileWatcher,
    restartFileWatcher,
  }
})
