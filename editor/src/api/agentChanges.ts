/*
 * Agent turn change API client.
 *
 * Usage:
 * Fetch the latest persisted change snapshot for a session or request its
 * guarded server-side undo. Components must not derive this from local diffs.
 */

import { apiGet, apiPost } from '@/api/client'
import { API_ROUTES } from '@/router/api_routes'

export interface AgentChangeEdit {
  path: string
  before: string | null
  after: string
  additions: number
  deletions: number
}

export interface AgentChangeFile {
  path: string
  additions: number
  deletions: number
  edits: AgentChangeEdit[]
}

export interface AgentChangeSnapshot {
  snapshot_id: string
  session_id: string
  run_id: string
  additions: number
  deletions: number
  is_undone: boolean
  is_imported?: boolean
  created_at: string
  files: AgentChangeFile[]
  edits: AgentChangeEdit[]
}

export interface AgentChangeResponse {
  change_snapshot: AgentChangeSnapshot | null
}

export function fetchSessionChanges(sessionId: string): Promise<AgentChangeResponse> {
  return apiGet<AgentChangeResponse>(API_ROUTES.SESSION_CHANGES(sessionId))
}

export function undoSessionChange(
  sessionId: string,
  snapshotId: string,
  userId: string,
): Promise<AgentChangeResponse> {
  return apiPost<AgentChangeResponse>(API_ROUTES.SESSION_CHANGE_UNDO(sessionId, snapshotId), {
    user_id: userId,
  })
}
