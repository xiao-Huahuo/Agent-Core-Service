/*
 * Knowledge workspace state store.
 *
 * Usage:
 * This store owns the backend file tree, editor tabs, command palette state,
 * and right-side Agent messages.
 */

import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'

import { ApiError } from '@/api/client'
import { updateCurrentDocumentContext } from '@/api/agent'
import {
  buildKnowledgeEventsUrl,
  copyKnowledgePath,
  createKnowledgeFile,
  createKnowledgeFolder,
  deleteKnowledgePath,
  ingestKnowledgeFileStream,
  ingestKnowledgePathStream,
  listKnowledgeFiles,
  previewKnowledgeFile,
  readKnowledgeFile,
  renameKnowledgePath,
  searchKnowledge,
  uploadKnowledgeFile,
  writeKnowledgeFile,
} from '@/api/knowledge'
import { rebuildKnowledgeRootStream } from '@/api/settings'
import type { KnowledgeIngestionProgressEvent } from '@/api/settings'
import { useSettingsStore } from '@/stores/settings'
import type {
  ChatMessage,
  CommandAction,
  EditorTab,
  EditorViewMode,
  FilePreviewPayload,
  FileViewerKind,
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

type FileConflictStrategy = 'overwrite' | 'skip' | 'rename'
type FileConflictDialogOwner = 'tree' | 'resources'

const MARKDOWN_EXTENSIONS = new Set(['md', 'markdown'])
const CODE_EXTENSIONS = new Set([
  'c',
  'cpp',
  'cs',
  'css',
  'go',
  'html',
  'java',
  'js',
  'json',
  'jsx',
  'kt',
  'php',
  'py',
  'rs',
  'sh',
  'sql',
  'ts',
  'tsx',
  'vue',
  'xml',
  'yaml',
  'yml',
])
const PREVIEW_ONLY_EXTENSIONS = new Set([
  'csv',
  'docx',
  'ppt',
  'pptx',
  'svg',
  'tsv',
  'xlsx',
])
const IMAGE_EXTENSIONS = new Set(['gif', 'jpeg', 'jpg', 'png', 'webp'])

function extensionOf(path: string): string {
  const name = getBaseName(path).toLowerCase()
  const dotIndex = name.lastIndexOf('.')
  return dotIndex >= 0 ? name.slice(dotIndex + 1) : ''
}

function viewerKindForPath(path: string): FileViewerKind {
  const extension = extensionOf(path)
  if (MARKDOWN_EXTENSIONS.has(extension)) return 'markdown'
  if (CODE_EXTENSIONS.has(extension)) return 'code'
  if (PREVIEW_ONLY_EXTENSIONS.has(extension)) return 'unsupported'
  return 'text'
}

function shouldUsePreviewEndpoint(path: string): boolean {
  return PREVIEW_ONLY_EXTENSIONS.has(extensionOf(path))
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

  /** Backend-generated multimodal preview cache for binary/table/document files. */
  const previewByPath = ref<Record<string, FilePreviewPayload>>({})

  /** Abort controller for the current preview fetch — cancels stale in-flight requests. */
  let _previewAbort: AbortController | null = null

  /** Abort controller for the current text-content fetch — cancels stale in-flight requests. */
  let _contentAbort: AbortController | null = null

  /** Paths currently being loaded via loadFilePreview (prevents duplicate concurrent loads). */
  const _pendingPreviewLoads = new Set<string>()

  /** Paths currently being loaded via loadFileContent (prevents duplicate concurrent loads). */
  const _pendingContentLoads = new Set<string>()

  /** Whether any file load is currently in-flight (for UI loading indicator). */
  const isFileLoading = ref(false)

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

  /** Header-level ingestion progress shown while uploads or rebuilds are running. */
  const ingestionProgressVisible = ref(false)
  const ingestionProgress = ref(0)
  const ingestionProgressStats = ref({ succeeded: 0, total: 0, failed: 0 })
  let ingestionProgressTimer: ReturnType<typeof setTimeout> | null = null
  let ingestionProgressPulseTimer: ReturnType<typeof setInterval> | null = null

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

  /**
   * Conflict resolution dialog state.
   *
   * When importing files that have name collisions at the target directory,
   * this dialog asks the user to pick a strategy: overwrite, skip, or rename.
   * The resolve callback is stored so the promptConflictStrategy Promise can
   * be settled from the template's button click handlers.
   */
  const conflictDialog = ref<{
    open: boolean
    owner: FileConflictDialogOwner
    targetDir: string
    conflictingNames: string[]
    resolve: ((strategy: FileConflictStrategy | null) => void) | null
  }>({
    open: false,
    owner: 'tree',
    targetDir: '',
    conflictingNames: [],
    resolve: null,
  })

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

  function setIngestionProgress(value: number) {
    ingestionProgress.value = Math.max(0, Math.min(100, Math.round(value)))
  }

  function stopIngestionProgressPulse() {
    if (ingestionProgressPulseTimer !== null) {
      clearInterval(ingestionProgressPulseTimer)
      ingestionProgressPulseTimer = null
    }
  }

  function beginIngestionProgress(initialValue = 6) {
    if (ingestionProgressTimer !== null) {
      clearTimeout(ingestionProgressTimer)
      ingestionProgressTimer = null
    }
    stopIngestionProgressPulse()
    ingestionProgressVisible.value = true
    ingestionProgressStats.value = { succeeded: 0, total: 0, failed: 0 }
    setIngestionProgress(initialValue)
  }

  function setIngestionProgressStats(succeeded: number, total: number, failed: number) {
    ingestionProgressStats.value = {
      succeeded: Math.max(0, succeeded),
      total: Math.max(0, total),
      failed: Math.max(0, failed),
    }
  }

  function applyIngestionProgressEvent(event: KnowledgeIngestionProgressEvent) {
    if (event.type === 'done' && event.result) {
      const total = Math.max(1, event.result.files_seen)
      setIngestionProgressStats(event.result.files_ingested, total, event.result.files_skipped)
      setIngestionProgress(98)
      return
    }
    const total = Math.max(1, Number(event.total ?? 0))
    const processed = Math.max(0, Math.min(total, Number(event.processed ?? 0)))
    const ratio = total > 0 ? processed / total : 0
    if (event.phase === 'frontmatter') {
      setIngestionProgress(8 + ratio * 34)
      setIngestionProgressStats(
        Number(event.files_written ?? processed),
        total,
        Number(event.files_skipped ?? 0),
      )
      return
    }
    if (event.phase === 'ingestion') {
      setIngestionProgress(42 + ratio * 50)
      setIngestionProgressStats(
        Number(event.files_ingested ?? processed),
        total,
        Number(event.files_skipped ?? 0),
      )
      return
    }
    if (event.phase === 'cleanup') {
      setIngestionProgress(96)
      return
    }
    if (event.phase === 'graph') {
      setIngestionProgress(event.status === 'finished' ? 98 : 97)
    }
  }

  function finishIngestionProgress(delay = 1000) {
    stopIngestionProgressPulse()
    setIngestionProgress(100)
    if (ingestionProgressTimer !== null) {
      clearTimeout(ingestionProgressTimer)
    }
    ingestionProgressTimer = setTimeout(() => {
      ingestionProgressVisible.value = false
      ingestionProgress.value = 0
      ingestionProgressTimer = null
    }, delay)
  }

  const flatNodes = computed(() => flattenNodes(tree.value))

  const selectedNode = computed(() => flatNodes.value.find((node) => node.path === selectedPath.value))

  const activeContent = computed(() => contentByPath.value[selectedPath.value] ?? '')

  const activePreview = computed(() => previewByPath.value[selectedPath.value] ?? null)

  const activeViewerKind = computed<FileViewerKind>(() => activePreview.value?.kind ?? viewerKindForPath(selectedPath.value))

  const activeFileReadonly = computed(() => Boolean(activePreview.value?.readonly) || shouldUsePreviewEndpoint(selectedPath.value))

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
    selectedTreePaths.value = new Set()
    selectionAnchorPath.value = path
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
      return
    }
    selectedPath.value = node.path
    if (!openTabs.value.some((tab) => tab.path === node.path)) {
      openTabs.value.push({ path: node.path, title: node.name, dirty: false, mtime: node.mtime })
    }
    // Fire-and-forget: loads run in background so rapid file switching
    // never blocks the UI or exhausts the browser connection pool.
    if (shouldUsePreviewEndpoint(node.path) || extensionOf(node.path) === 'pdf' || IMAGE_EXTENSIONS.has(extensionOf(node.path))) {
      if (previewByPath.value[node.path] === undefined) {
        loadFilePreview(node.path)
      }
    } else if (contentByPath.value[node.path] === undefined) {
      loadFileContent(node.path)
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
    if (!selectedPath.value || activeFileReadonly.value) {
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
    if (!tab || !selectedPath.value || activeFileReadonly.value) {
      return
    }
    await saveFileByPath(tab.path)
  }

  async function saveFileByPath(path: string) {
    const tab = openTabs.value.find((item) => item.path === path)
    if (!tab || shouldUsePreviewEndpoint(path)) {
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

  function basenameOfPath(path: string): string {
    return path.replace(/\\/g, '/').split('/').filter(Boolean).pop() ?? path
  }

  function childNamesInDirectory(targetDirPath: string): Set<string> {
    const targetDir = normalizeTreePath(targetDirPath)
    return new Set(
      flatNodes.value
        .filter((node) => getParentPath(node.path) === targetDir)
        .map((node) => node.name),
    )
  }

  function hasNameConflict(targetDirPath: string, names: string[]): boolean {
    const existingNames = childNamesInDirectory(targetDirPath)
    return names.some((name) => existingNames.has(name))
  }

  /**
   * Checks whether ANY of the given names already exist in the target dir.
   * If no conflict, returns immediately with 'overwrite' (no dialog needed).
   * On conflict it opens the conflict dialog and returns a Promise that
   * resolves with the user's choice when they click a button.
   *
   * The resolve callback is stored in conflictDialog.value.resolve so the
   * FileTreePanel dialog template can settle it via resolveConflict().
   */
  function promptConflictStrategy(
    targetDirPath: string,
    names: string[],
    owner: FileConflictDialogOwner = 'tree',
  ): Promise<FileConflictStrategy | null> {
    return new Promise((resolve) => {
      const targetDir = normalizeTreePath(targetDirPath)
      if (!hasNameConflict(targetDir, names)) {
        resolve('overwrite')
        return
      }
      const existingNames = childNamesInDirectory(targetDir)
      const conflictingNames = names.filter((name) => existingNames.has(name))
      conflictDialog.value = {
        open: true,
        owner,
        targetDir,
        conflictingNames,
        resolve,
      }
    })
  }

  /** Called by the conflict dialog's "覆盖" button. */
  function resolveConflict(strategy: FileConflictStrategy) {
    const resolve = conflictDialog.value.resolve
    conflictDialog.value = {
      open: false,
      owner: 'tree',
      targetDir: '',
      conflictingNames: [],
      resolve: null,
    }
    resolve?.(strategy)
  }

  /** Called by the conflict dialog's "取消" / backdrop click. */
  function cancelConflict() {
    const resolve = conflictDialog.value.resolve
    conflictDialog.value = {
      open: false,
      owner: 'tree',
      targetDir: '',
      conflictingNames: [],
      resolve: null,
    }
    resolve?.(null)
  }

  async function importFilesToPath(
    files: File[],
    targetDirPath = '',
    conflictStrategy?: FileConflictStrategy,
    conflictOwner: FileConflictDialogOwner = 'tree',
  ) {
    const targetPath = normalizeTreePath(targetDirPath)
    let importedFiles = files.filter((file) => file.name)
    if (importedFiles.length === 0) {
      return
    }
    const strategy = conflictStrategy
      ?? await promptConflictStrategy(targetPath, importedFiles.map((file) => file.name), conflictOwner)
    if (!strategy) {
      return
    }
    if (strategy === 'skip') {
      const existingNames = childNamesInDirectory(targetPath)
      importedFiles = importedFiles.filter((file) => !existingNames.has(file.name))
      if (importedFiles.length === 0) {
        showToast('已跳过 — 所有选中文件已存在')
        return
      }
    }
    const existingNames = strategy === 'overwrite' ? childNamesInDirectory(targetPath) : new Set<string>()
    const settingsStore = useSettingsStore()
    ignoreNextTreeEvent.value += 3
    const uploaded: string[] = []
    const failed: string[] = []
    try {
      for (const [index, file] of importedFiles.entries()) {
        try {
          // When overwriting, delete existing file first so the backend
          // cleans up its vector-library entries before the new copy lands.
          if (strategy === 'overwrite' && existingNames.has(file.name)) {
            const existingPath = joinTreePath(targetPath, file.name)
            ignoreNextTreeEvent.value += 1
            await deleteKnowledgePath(settingsStore.profile.userId, existingPath)
          }
          await uploadKnowledgeFile(
            settingsStore.profile.userId,
            file,
            targetPath,
            Boolean(settingsStore.profile.autoIngestOnUpload),
            strategy,
          )
          uploaded.push(file.name)
        } catch {
          failed.push(file.name)
        }
      }
      await loadKnowledgeTree()
      selectedTreePath.value = targetPath
      syncCurrentDocumentContext()
      if (failed.length === 0 && uploaded.length > 0) {
        const suffix = settingsStore.profile.autoIngestOnUpload ? '并已灌库' : ''
        showToast(`已导入 ${uploaded.length} 个文件${suffix}`)
      } else if (failed.length > 0 && uploaded.length > 0) {
        showToast(`已导入 ${uploaded.length} 个, 跳过 ${failed.length} 个`)
      } else if (failed.length > 0) {
        showToast(`导入失败 ${failed.length} 个文件`)
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : '请检查连接'
      showToast(`导入失败 — ${message}`)
    }
  }

  async function importExternalPathsToPath(
    paths: string[],
    targetDirPath = '',
    conflictStrategy?: FileConflictStrategy,
    conflictOwner: FileConflictDialogOwner = 'tree',
  ) {
    const desktop = window.agentEditorDesktop
    if (!desktop?.copyExternalPathsIntoDirectory) {
      return
    }
    const sourcePaths = paths.map((item) => item.trim()).filter(Boolean)
    if (sourcePaths.length === 0) {
      return
    }
    const targetPath = normalizeTreePath(targetDirPath)
    const strategy = conflictStrategy
      ?? await promptConflictStrategy(targetPath, sourcePaths.map(basenameOfPath), conflictOwner)
    if (!strategy) {
      return
    }
    const effectivePaths = strategy === 'skip'
      ? sourcePaths.filter((item) => !childNamesInDirectory(targetPath).has(basenameOfPath(item)))
      : sourcePaths
    if (effectivePaths.length === 0) {
      showToast('已跳过 — 所有选中文件已存在')
      return
    }
    // When overwriting, delete existing files via backend first so
    // the vector-library entries are cleaned up before the new copy lands.
    if (strategy === 'overwrite') {
      const settingsStore = useSettingsStore()
      const existingNames = childNamesInDirectory(targetPath)
      for (const item of effectivePaths) {
        const name = basenameOfPath(item)
        if (existingNames.has(name)) {
          const existingPath = joinTreePath(targetPath, name)
          ignoreNextTreeEvent.value += 1
          await deleteKnowledgePath(settingsStore.profile.userId, existingPath).catch(() => {})
        }
      }
    }
    const targetAbsoluteDir = buildAbsoluteKnowledgePath(useSettingsStore().profile.knowledgeDir, targetPath)
    ignoreNextTreeEvent.value += effectivePaths.length
    try {
      const result = await desktop.copyExternalPathsIntoDirectory(effectivePaths, targetAbsoluteDir, 'copy', strategy)
      await loadKnowledgeTree()
      if (result.paths.length > 0) {
        const root = useSettingsStore().profile.knowledgeDir.replace(/[\\/]+$/g, '')
        const relativePaths = result.paths.map((path) => normalizeTreePath(path.replace(root, '')))
        setTreeSelection(relativePaths, relativePaths[relativePaths.length - 1] ?? '')
        showToast(`已导入 ${result.paths.length} 项`)
      } else {
        showToast('导入已跳过')
      }
      syncCurrentDocumentContext()
    } catch (error) {
      const message = error instanceof Error ? error.message : '请检查连接'
      showToast(`导入失败 — ${message}`)
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
    previewByPath.value = {}
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
    beginIngestionProgress(10)
    tree.value = tree.value.map((node) => ({ ...node, indexStatus: 'indexing' }))
    const settingsStore = useSettingsStore()
    if (!settingsStore.profile.userId) {
      refreshing.value = false
      finishIngestionProgress()
      return
    }
    try {
      await loadKnowledgeTree()
      setIngestionProgress(22)
      if (activeTab.value && !shouldUsePreviewEndpoint(activeTab.value.path)) {
        const tab = activeTab.value
        const response = await readKnowledgeFile(settingsStore.profile.userId, tab.path)
        contentByPath.value = { ...contentByPath.value, [tab.path]: response.content }
        tab.dirty = false
        tab.mtime = response.mtime
      }
      setIngestionProgress(34)
      const result = await rebuildKnowledgeRootStream(settingsStore.profile.userId, applyIngestionProgressEvent)
      await loadKnowledgeTree()
      setIngestionProgressStats(result.files_ingested, result.files_seen, result.files_skipped)
      setIngestionProgress(98)
      showToast(`灌库完成 — ${result.files_ingested} 个文件重新索引`)
    } catch (error) {
      setIngestionProgressStats(0, 1, 1)
      const message = error instanceof Error ? error.message : '请检查连接'
      showToast(`灌库失败 — ${message}`)
    } finally {
      refreshing.value = false
      finishIngestionProgress()
    }
  }

  async function ingestFile(node: KnowledgeFileNode) {
    if (refreshing.value) return
    const settingsStore = useSettingsStore()
    if (!settingsStore.profile.userId) return
    refreshing.value = true
    beginIngestionProgress(12)
    try {
      const api = node.isDir ? ingestKnowledgePathStream : ingestKnowledgeFileStream
      const result = await api(settingsStore.profile.userId, node.path, applyIngestionProgressEvent) as {
        files_seen?: number
        files_ingested?: number
        files_skipped?: number
        chunks_created?: number
        skip_reason?: string
        status_message?: string
      }
      const total = Math.max(1, result.files_seen ?? ((result.files_ingested ?? 0) + (result.files_skipped ?? 0)))
      setIngestionProgressStats(result.files_ingested ?? 0, total, result.files_skipped ?? 0)
      setIngestionProgress(98)
      await loadKnowledgeTree()
      if ((result.files_ingested ?? 0) > 0) {
        showToast(`已灌库 ${result.files_ingested ?? 0} 个文件, ${result.chunks_created ?? 0} 个切片`)
      } else if (result.status_message) {
        showToast(result.status_message)
      } else {
        showToast('跳过不支持或已屏蔽的文件')
      }
    } catch (error) {
      setIngestionProgressStats(0, 1, 1)
      const message = error instanceof Error ? error.message : '未知错误'
      showToast(`灌库失败 — ${message}`)
    } finally {
      refreshing.value = false
      finishIngestionProgress()
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

  /**
   * Writes the absolute paths of selected tree nodes to the system clipboard.
   *
   * On Electron/Windows the main process writes a real FileDropList to the
   * native clipboard, which File Explorer recognises as file paths for paste.
   * When Electron is unavailable we fall back to writing plain text paths via
   * the Web Clipboard API.
   *
   * IMPORTANT: we must NOT call both APIs — the second call would overwrite
   * the formats set by the first, breaking external paste.
   */
  async function copyNodesToSystemClipboard(nodes: KnowledgeFileNode[], mode: 'copy' | 'cut') {
    const settingsStore = useSettingsStore()
    const absolutePaths = nodes.map((node) => buildAbsoluteKnowledgePath(settingsStore.profile.knowledgeDir, node.path))
    if (window.agentEditorDesktop?.copyFilePaths) {
      const copied = await window.agentEditorDesktop.copyFilePaths(absolutePaths, mode)
      if (!copied) {
        showToast('复制失败 — 无法写入系统文件剪贴板')
        return
      }
      showToast(mode === 'cut' ? `已剪切 ${absolutePaths.length} 项` : `已复制 ${absolutePaths.length} 项`)
      return
    }
    await navigator.clipboard?.writeText(absolutePaths.join('\n'))
    showToast(mode === 'cut' ? `已复制路径 ${absolutePaths.length} 项` : `已复制路径 ${absolutePaths.length} 项`)
  }

  async function pasteNode(targetNode?: KnowledgeFileNode | null, conflictOwner: FileConflictDialogOwner = 'tree') {
    const pending = fileClipboard.value
    if (!pending || pending.nodes.length === 0) {
      await pasteExternalClipboardPaths(targetNode, conflictOwner)
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

  async function pasteExternalClipboardPaths(
    targetNode?: KnowledgeFileNode | null,
    conflictOwner: FileConflictDialogOwner = 'tree',
  ) {
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
    const strategy = await promptConflictStrategy(targetDir, sourcePaths.map(basenameOfPath), conflictOwner)
    if (!strategy) {
      return
    }
    const effectiveSourcePaths = strategy === 'skip'
      ? sourcePaths.filter((item) => !childNamesInDirectory(targetDir).has(basenameOfPath(item)))
      : sourcePaths
    if (effectiveSourcePaths.length === 0) {
      showToast('粘贴已跳过 — 所有文件已存在')
      return
    }
    // When overwriting, delete existing files via backend first so
    // the vector-library entries are cleaned up before the new copy.
    if (strategy === 'overwrite') {
      const settingsStore = useSettingsStore()
      const existingNames = childNamesInDirectory(targetDir)
      for (const item of effectiveSourcePaths) {
        const name = basenameOfPath(item)
        if (existingNames.has(name)) {
          const existingPath = joinTreePath(targetDir, name)
          ignoreNextTreeEvent.value += 1
          await deleteKnowledgePath(settingsStore.profile.userId, existingPath).catch(() => {})
        }
      }
    }
    ignoreNextTreeEvent.value += effectiveSourcePaths.length
    const result = await desktop.copyExternalPathsIntoDirectory(
      effectiveSourcePaths,
      targetAbsoluteDir,
      clipboardFiles.mode,
      strategy,
    )
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
    try {
      await deleteKnowledgePath(settingsStore.profile.userId, node.path)
    } catch (err: unknown) {
      ignoreNextTreeEvent.value -= 1
      showToast(err instanceof ApiError ? err.message : '删除失败')
      await loadKnowledgeTree()
      return
    }
    openTabs.value = openTabs.value.filter((tab) => !isSameOrChildPath(tab.path, node.path))
    Object.keys(contentByPath.value).forEach((path) => {
      if (isSameOrChildPath(path, node.path)) {
        delete contentByPath.value[path]
      }
    })
    Object.keys(previewByPath.value).forEach((path) => {
      if (isSameOrChildPath(path, node.path)) {
        delete previewByPath.value[path]
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

  async function loadFileContent(path: string): Promise<void> {
    if (_pendingContentLoads.has(path)) return
    _pendingContentLoads.add(path)
    isFileLoading.value = true
    // Abort previous content fetch — user switched to a different file.
    _contentAbort?.abort()
    const controller = new AbortController()
    _contentAbort = controller
    let timedOut = false
    const timeoutTimer = setTimeout(() => {
      timedOut = true
      controller.abort()
    }, 8_000)
    try {
      const settingsStore = useSettingsStore()
      const response = await readKnowledgeFile(settingsStore.profile.userId, path, controller.signal)
      // Stale guard: if user switched away while this request was in-flight, skip.
      if (selectedPath.value !== path) return
      contentByPath.value = { ...contentByPath.value, [path]: response.content }
      const nextPreview = { ...previewByPath.value }
      delete nextPreview[path]
      previewByPath.value = nextPreview
      const tab = openTabs.value.find((t) => t.path === path)
      if (tab) tab.mtime = response.mtime
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        if (timedOut) {
          showToast(`文件加载超时 (${path})`)
          contentByPath.value = { ...contentByPath.value, [path]: '' }
        }
        return
      }
      const msg = err instanceof ApiError ? err.message : '读取文件内容失败'
      showToast(msg)
    } finally {
      clearTimeout(timeoutTimer)
      _pendingContentLoads.delete(path)
      if (_contentAbort === controller) {
        _contentAbort = null
        isFileLoading.value = false
      }
    }
    syncCurrentDocumentContext()
  }

  async function loadFilePreview(path: string): Promise<void> {
    if (_pendingPreviewLoads.has(path)) return
    _pendingPreviewLoads.add(path)
    isFileLoading.value = true
    // Abort previous preview fetch — user switched to a different file.
    _previewAbort?.abort()
    const controller = new AbortController()
    _previewAbort = controller
    let timedOut = false
    const timeoutTimer = setTimeout(() => {
      timedOut = true
      controller.abort()
    }, 15_000)
    try {
      const settingsStore = useSettingsStore()
      const response = await previewKnowledgeFile(settingsStore.profile.userId, path, controller.signal)
      // Stale guard: if user switched away while this request was in-flight, skip.
      if (selectedPath.value !== path) return
      previewByPath.value = { ...previewByPath.value, [path]: response }
      if (response.content !== undefined) {
        contentByPath.value = { ...contentByPath.value, [path]: response.content }
      }
      const tab = openTabs.value.find((t) => t.path === path)
      if (tab) tab.mtime = response.mtime
    } catch (err: unknown) {
      // Silent abort — user navigated away from this file.
      if (err instanceof DOMException && err.name === 'AbortError') {
        if (timedOut) {
          showToast(`文件预览超时 (${path})`)
          previewByPath.value = {
            ...previewByPath.value,
            [path]: {
              path,
              kind: 'unsupported' as const,
              message: '预览加载超时',
              mtime: '',
              size: 0,
              extension: '',
              readonly: true,
            },
          }
        }
        return
      }
      showToast(err instanceof ApiError ? err.message : '文件预览加载失败')
      previewByPath.value = {
        ...previewByPath.value,
        [path]: {
          path,
          kind: 'unsupported' as const,
          message: '预览加载失败',
          mtime: '',
          size: 0,
          extension: '',
          readonly: true,
        },
      }
    } finally {
      clearTimeout(timeoutTimer)
      _pendingPreviewLoads.delete(path)
      if (_previewAbort === controller) {
        _previewAbort = null
        isFileLoading.value = false
      }
    }
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
    for (let index = 1; index < 1000; index += 1) {
      const candidate = joinTreePath(parentDirPath, `${stem} (${index})${extension}`)
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
    Object.entries(previewByPath.value).forEach(([path, preview]) => {
      if (!isSameOrChildPath(path, sourcePath)) {
        return
      }
      const nextPath = path.replace(sourcePath, targetPath)
      delete previewByPath.value[path]
      previewByPath.value[nextPath] = { ...preview, path: nextPath }
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
    activePreview,
    activeViewerKind,
    activeFileReadonly,
    activeTab,
    dirtyFilePaths,
    hasDirtyTabs,
    isFileLoading,
    commandPaletteOpen,
    chatMessages,
    commands,
    treeLoading,
    fileClipboard,
    conflictDialog,
    refreshing,
    ingestionProgress,
    ingestionProgressStats,
    ingestionProgressVisible,
    toastMessage,
    toastVisible,
    showToast,
    resolveConflict,
    cancelConflict,
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
    importExternalPathsToPath,
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
    ingestFile,
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
