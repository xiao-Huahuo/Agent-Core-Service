/*
 * Session API for the editor Agent panel.
 *
 * Usage:
 * Mirrors the console session endpoints so chat history is shared between
 * console and editor for the same user_id.
 */

import { ApiError, apiDelete, apiGet, apiPost, apiPut } from '@/api/client'
import { API_ROUTES } from '@/router/api_routes'

const LOCAL_BACKEND_ORIGIN = 'http://127.0.0.1:8002'

export interface SessionRecord {
  session_id: string
  user_id: string
  session_name: string
  created_at: string
  updated_at: string
}

export interface SessionMessageRecord {
  message_id: string
  session_id: string
  role: string
  content: string
  tool_call_id?: string
  tool_calls?: unknown[]
  metadata?: Record<string, unknown>
  created_at: string
}

export interface SessionStateResponse {
  session_state: Record<string, unknown> | null
}

export function listSessions(userId: string): Promise<SessionRecord[]> {
  return apiGet<SessionRecord[]>('/sessions', { user_id: userId })
}

export function createSession(userId: string, sessionName?: string): Promise<SessionRecord> {
  return apiPost<SessionRecord>('/sessions', {
    user_id: userId,
    session_name: sessionName || undefined,
  })
}

export function fetchMessages(
  sessionId: string,
  userId: string,
  limit?: number,
  options: { signal?: AbortSignal } = {},
): Promise<SessionMessageRecord[]> {
  return apiGet<SessionMessageRecord[]>(`/sessions/${sessionId}/messages`, { user_id: userId, limit }, {
    signal: options.signal,
  })
}

export function fetchSessionState(sessionId: string): Promise<SessionStateResponse> {
  return apiGet<SessionStateResponse>(API_ROUTES.SESSION_STATE(sessionId))
}

export function saveSessionEnvironment(
  sessionId: string,
  environment: Record<string, string>,
): Promise<SessionStateResponse> {
  return apiPut<SessionStateResponse>(API_ROUTES.SESSION_STATE(sessionId), { environment })
}

/**
 * Fetch every persisted message owned by one user across all sessions.
 *
 * The dashboard uses this endpoint for long-term RAG and latency charts so
 * their scope does not depend on the currently selected chat session. During
 * a rolling frontend/backend upgrade, retry the dedicated backend origin when
 * a frontend HTML fallback is returned. Missing range support fails explicitly
 * instead of issuing one request per Session.
 */
export async function fetchUserMessageHistory(
  userId: string,
  turnLimit?: number,
): Promise<SessionMessageRecord[]> {
  const query = { user_id: userId, limit: turnLimit }
  try {
    return await apiGet<SessionMessageRecord[]>(API_ROUTES.SESSION_MESSAGE_HISTORY, query)
  } catch (historyError) {
    if (!isHistoryRouteUnavailable(historyError)) {
      throw historyError
    }
    if (historyError instanceof SyntaxError) {
      try {
        return await apiGet<SessionMessageRecord[]>(
          `${LOCAL_BACKEND_ORIGIN}${API_ROUTES.SESSION_MESSAGE_HISTORY}`,
          query,
        )
      } catch (directError) {
        if (!isHistoryRouteUnavailable(directError)) {
          throw directError
        }
      }
    }
  }

  throw new ApiError(503, '观测历史范围接口不可用，请重启后端服务后重试')
}

/** Identify a missing route or an SPA HTML fallback without hiding real API failures. */
function isHistoryRouteUnavailable(error: unknown): boolean {
  return error instanceof SyntaxError
    || (error instanceof ApiError && (error.status === 404 || error.status === 405))
}

export function deleteSession(sessionId: string): Promise<{ ok: boolean }> {
  return apiDelete<{ ok: boolean }>(`/sessions/${sessionId}`)
}

export function clearAllSessions(userId: string): Promise<{ ok: boolean; deleted_count: number }> {
  return apiDelete<{ ok: boolean; deleted_count: number }>('/sessions', { user_id: userId })
}

export function pruneEmptySessions(userId: string): Promise<{ ok: boolean; pruned_count: number }> {
  return apiPost<{ ok: boolean; pruned_count: number }>('/sessions/prune', { user_id: userId })
}

export interface ImportedMessage {
  role: string
  content: string
  created_at?: string
  node?: string
  reference?: string
  tool_calls?: unknown[]
  trace_details?: unknown[]
  child_agent_event?: unknown
  tool_call_id?: string
  metadata?: Record<string, unknown>
}

export function importSession(
  userId: string,
  messages: ImportedMessage[],
  sessionName?: string,
): Promise<{
  session_id: string
  user_id: string
  session_name: string
  created_at: string
  updated_at: string
  imported_count: number
}> {
  return apiPost('/sessions/import', {
    user_id: userId,
    session_name: sessionName,
    messages,
  })
}

export function importSessionFile(
  userId: string,
  content: string,
  sessionName?: string,
): Promise<{
  session_id: string
  user_id: string
  session_name: string
  created_at: string
  updated_at: string
  imported_count: number
}> {
  return apiPost('/sessions/import-file', {
    user_id: userId,
    content,
    session_name: sessionName,
  })
}

export function updateSessionName(
  sessionId: string,
  sessionName: string,
): Promise<{ session_id: string; session_name: string; updated_at: string }> {
  return apiPut<{ session_id: string; session_name: string; updated_at: string }>(`/sessions/${sessionId}/name`, {
    session_name: sessionName,
  })
}
