/*
 * Knowledge-library Git API client.
 *
 * Usage:
 * Git stores and components call these typed helpers instead of embedding
 * endpoint strings or interpreting raw Git command output.
 */

import { apiGet, apiPost } from '@/api/client'
import { API_ROUTES } from '@/router/api_routes'

export type GitFileState =
  | 'modified'
  | 'added'
  | 'deleted'
  | 'renamed'
  | 'conflicted'
  | 'untracked'

export interface GitFileChange {
  path: string
  name: string
  directory: string
  old_path: string
  code: string
  state: GitFileState
  staged: boolean
  working_tree: boolean
}

export interface GitBranchInfo {
  name: string
  upstream: string
  current: boolean
}

export interface GitStatus {
  initialized: boolean
  repository_root: string
  current_branch: string
  upstream: string
  ahead: number
  behind: number
  detached: boolean
  branches: GitBranchInfo[]
  remote_branches: string[]
  remotes: string[]
  changes: GitFileChange[]
  untracked: GitFileChange[]
  has_changes: boolean
}

export interface GitCommitInfo {
  hash: string
  short_hash: string
  author: string
  date: string
  summary: string
}

export interface GitHistoryPayload {
  history: GitCommitInfo[]
  unpushed_commits: GitCommitInfo[]
  unpushed_files: Array<{ path: string; status: string }>
  upstream: string
}

export interface GitCommitResult {
  ok: boolean
  commit: string
  short_commit: string
  summary: string
  status: GitStatus
}

export function fetchGitStatus(userId: string): Promise<GitStatus> {
  return apiGet<GitStatus>(API_ROUTES.GIT_STATUS, { user_id: userId })
}

export function initializeGitRepository(userId: string, initialBranch = 'main'): Promise<GitStatus> {
  return apiPost<GitStatus>(API_ROUTES.GIT_INIT, {
    user_id: userId,
    initial_branch: initialBranch,
  })
}

export function fetchGitHistory(userId: string, limit = 50): Promise<GitHistoryPayload> {
  return apiGet<GitHistoryPayload>(API_ROUTES.GIT_HISTORY, {
    user_id: userId,
    limit,
  })
}

export function fetchGitDiff(userId: string, path = '', staged = false): Promise<{ diff: string }> {
  return apiGet<{ diff: string }>(API_ROUTES.GIT_DIFF, {
    user_id: userId,
    path,
    staged,
  })
}

export function restoreGitPaths(
  userId: string,
  paths: string[],
): Promise<{ ok: boolean; restored: string[]; trashed: string[]; status: GitStatus }> {
  return apiPost(API_ROUTES.GIT_RESTORE, { user_id: userId, paths })
}

export function commitGitPaths(
  userId: string,
  paths: string[],
  message: string,
): Promise<GitCommitResult> {
  return apiPost<GitCommitResult>(API_ROUTES.GIT_COMMIT, {
    user_id: userId,
    paths,
    message,
  })
}

export function pushGitBranch(
  userId: string,
  options: {
    localBranch: string
    remote: string
    remoteBranch: string
    forceWithLease?: boolean
    allBranches?: boolean
  },
): Promise<{ ok: boolean; status: GitStatus; output: string; all_branches: boolean }> {
  return apiPost(API_ROUTES.GIT_PUSH, {
    user_id: userId,
    local_branch: options.localBranch,
    remote: options.remote,
    remote_branch: options.remoteBranch,
    force_with_lease: options.forceWithLease ?? false,
    set_upstream: true,
    all_branches: options.allBranches ?? false,
  })
}

export function createGitBranch(
  userId: string,
  name: string,
  checkout = false,
): Promise<GitStatus> {
  /** Create a local branch, optionally switching the worktree to it. */

  return apiPost<GitStatus>(API_ROUTES.GIT_BRANCHES, {
    user_id: userId,
    name,
    checkout,
  })
}

export function addGitRemote(userId: string, name: string, url: string): Promise<GitStatus> {
  /** Register a named remote repository for the active knowledge library. */

  return apiPost<GitStatus>(API_ROUTES.GIT_REMOTES, {
    user_id: userId,
    name,
    url,
  })
}

export function switchGitBranch(userId: string, name: string): Promise<GitStatus> {
  /** Switch the active knowledge library worktree to an existing local branch. */

  return apiPost<GitStatus>(API_ROUTES.GIT_SWITCH, {
    user_id: userId,
    name,
  })
}
