/*
 * Git sidebar state store.
 *
 * Usage:
 * Both the left and right Git sidebars share this store so selection, commit
 * text, repository status and dialogs remain synchronized.
 */

import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import {
  addGitRemote,
  commitGitPaths,
  createGitBranch,
  fetchGitHistory,
  fetchGitStatus,
  initializeGitRepository,
  pushGitBranch,
  restoreGitPaths,
  type GitFileChange,
  type GitHistoryPayload,
  type GitStatus,
} from '@/api/git'
import { ApiError } from '@/api/client'
import { useSettingsStore } from '@/stores/settings'
import { useWorkspaceStore } from '@/stores/workspace'

const EMPTY_STATUS: GitStatus = {
  initialized: false,
  repository_root: '',
  current_branch: '',
  upstream: '',
  ahead: 0,
  behind: 0,
  detached: false,
  branches: [],
  remote_branches: [],
  remotes: [],
  changes: [],
  untracked: [],
  has_changes: false,
}

export const useGitStore = defineStore('git', () => {
  /** Latest repository status returned by the backend. */
  const status = ref<GitStatus>({ ...EMPTY_STATUS })

  /** Paths selected for restore or commit. */
  const selectedPaths = ref<Set<string>>(new Set())

  /** Commit summary shared by both sidebars. */
  const commitMessage = ref('')

  /** Group expansion state. */
  const changesExpanded = ref(true)
  const untrackedExpanded = ref(true)

  /** Request and dialog state. */
  const loading = ref(false)
  const mutating = ref(false)
  const historyOpen = ref(false)
  const pushOpen = ref(false)
  const history = ref<GitHistoryPayload>({
    history: [],
    unpushed_commits: [],
    unpushed_files: [],
    upstream: '',
  })
  const errorMessage = ref('')

  const allFiles = computed(() => [...status.value.changes, ...status.value.untracked])
  const selectedFiles = computed(() => (
    allFiles.value.filter((item) => selectedPaths.value.has(item.path))
  ))
  const selectedCount = computed(() => selectedFiles.value.length)
  const fileStatusMap = computed(() => {
    const result = new Map<string, GitFileChange>()
    for (const item of allFiles.value) {
      result.set(item.path.replace(/\\/g, '/'), item)
    }
    return result
  })

  function userId(): string {
    return useSettingsStore().profile.userId
  }

  function syncSelection(): void {
    const available = new Set(allFiles.value.map((item) => item.path))
    selectedPaths.value = new Set(
      [...selectedPaths.value].filter((path) => available.has(path)),
    )
  }

  function readableError(error: unknown): string {
    if (error instanceof ApiError) return error.message
    if (error instanceof Error) return error.message
    return 'Git 操作失败'
  }

  async function refresh(): Promise<void> {
    const currentUserId = userId()
    if (!currentUserId || loading.value) return
    loading.value = true
    errorMessage.value = ''
    try {
      status.value = await fetchGitStatus(currentUserId)
      syncSelection()
    } catch (error) {
      errorMessage.value = readableError(error)
    } finally {
      loading.value = false
    }
  }

  async function initialize(initialBranch = 'main'): Promise<void> {
    mutating.value = true
    errorMessage.value = ''
    try {
      status.value = await initializeGitRepository(userId(), initialBranch)
    } catch (error) {
      errorMessage.value = readableError(error)
      throw error
    } finally {
      mutating.value = false
    }
  }

  function togglePath(path: string): void {
    const next = new Set(selectedPaths.value)
    if (next.has(path)) next.delete(path)
    else next.add(path)
    selectedPaths.value = next
  }

  function setGroupSelection(files: GitFileChange[], selected: boolean): void {
    const next = new Set(selectedPaths.value)
    for (const item of files) {
      if (selected) next.add(item.path)
      else next.delete(item.path)
    }
    selectedPaths.value = next
  }

  function isGroupSelected(files: GitFileChange[]): boolean {
    return files.length > 0 && files.every((item) => selectedPaths.value.has(item.path))
  }

  function expandAll(): void {
    changesExpanded.value = true
    untrackedExpanded.value = true
  }

  function collapseAll(): void {
    changesExpanded.value = false
    untrackedExpanded.value = false
  }

  async function restoreSelected(): Promise<void> {
    if (selectedCount.value === 0) return
    mutating.value = true
    errorMessage.value = ''
    try {
      const result = await restoreGitPaths(userId(), selectedFiles.value.map((item) => item.path))
      status.value = result.status
      selectedPaths.value = new Set()
      await useWorkspaceStore().loadKnowledgeTree()
      useWorkspaceStore().showToast(
        result.trashed.length > 0
          ? `已回滚 ${result.restored.length} 个文件，${result.trashed.length} 个未跟踪文件已移入最近删除`
          : `已回滚 ${result.restored.length} 个文件`,
      )
    } catch (error) {
      errorMessage.value = readableError(error)
      throw error
    } finally {
      mutating.value = false
    }
  }

  async function commitSelected(): Promise<void> {
    const message = commitMessage.value.trim()
    if (selectedCount.value === 0 || !message) return
    mutating.value = true
    errorMessage.value = ''
    try {
      const result = await commitGitPaths(
        userId(),
        selectedFiles.value.map((item) => item.path),
        message,
      )
      status.value = result.status
      selectedPaths.value = new Set()
      commitMessage.value = ''
      useWorkspaceStore().showToast(`已提交 ${result.short_commit}`)
    } catch (error) {
      errorMessage.value = readableError(error)
      throw error
    } finally {
      mutating.value = false
    }
  }

  async function loadHistory(): Promise<void> {
    errorMessage.value = ''
    try {
      history.value = await fetchGitHistory(userId())
    } catch (error) {
      errorMessage.value = readableError(error)
      throw error
    }
  }

  async function openHistory(): Promise<void> {
    await loadHistory()
    historyOpen.value = true
  }

  async function openPush(): Promise<void> {
    await loadHistory()
    pushOpen.value = true
  }

  async function push(options: {
    localBranch: string
    remote: string
    remoteBranch: string
    forceWithLease?: boolean
    allBranches?: boolean
  }): Promise<void> {
    mutating.value = true
    errorMessage.value = ''
    try {
      const result = await pushGitBranch(userId(), options)
      status.value = result.status
      pushOpen.value = false
      await loadHistory()
      useWorkspaceStore().showToast('推送完成')
    } catch (error) {
      errorMessage.value = readableError(error)
      throw error
    } finally {
      mutating.value = false
    }
  }

  async function ensureLocalBranch(name: string): Promise<void> {
    /** Create a typed local branch only when it is not already available. */

    if (status.value.branches.some((branch) => branch.name === name)) return
    status.value = await createGitBranch(userId(), name, false)
  }

  async function ensureRemote(name: string, url: string): Promise<void> {
    /** Add a typed remote only when it is not already configured. */

    if (status.value.remotes.includes(name)) return
    status.value = await addGitRemote(userId(), name, url)
  }

  function useHistoryMessage(summary: string): void {
    commitMessage.value = summary
    historyOpen.value = false
  }

  function statusForPath(path: string): GitFileChange | undefined {
    return fileStatusMap.value.get(path.replace(/\\/g, '/'))
  }

  function reset(): void {
    status.value = { ...EMPTY_STATUS }
    selectedPaths.value = new Set()
    commitMessage.value = ''
    historyOpen.value = false
    pushOpen.value = false
    errorMessage.value = ''
  }

  return {
    status,
    selectedPaths,
    commitMessage,
    changesExpanded,
    untrackedExpanded,
    loading,
    mutating,
    historyOpen,
    pushOpen,
    history,
    errorMessage,
    allFiles,
    selectedFiles,
    selectedCount,
    fileStatusMap,
    refresh,
    initialize,
    togglePath,
    setGroupSelection,
    isGroupSelected,
    expandAll,
    collapseAll,
    restoreSelected,
    commitSelected,
    loadHistory,
    openHistory,
    openPush,
    push,
    ensureLocalBranch,
    ensureRemote,
    useHistoryMessage,
    statusForPath,
    reset,
  }
})
