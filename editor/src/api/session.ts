/*
 * Session API for the editor Agent panel.
 *
 * Usage:
 * Mirrors the console session endpoints so chat history is shared between
 * console and editor for the same user_id.
 */

import { apiDelete, apiGet, apiPost, apiPut } from '@/api/client'

export interface SessionRecord {
  session_id: string
  user_id: string
  session_name: string
  created_at: string
  updated_at: string
}

export interface SessionMessageRecord {
  message_id: string
  role: string
  content: string
  tool_calls?: unknown[]
  metadata?: Record<string, unknown>
  created_at: string
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
  limit = 50,
  options: { signal?: AbortSignal } = {},
): Promise<SessionMessageRecord[]> {
  return apiGet<SessionMessageRecord[]>(`/sessions/${sessionId}/messages`, { user_id: userId, limit }, {
    signal: options.signal,
  })
}

export function deleteSession(sessionId: string): Promise<{ ok: boolean }> {
  return apiDelete<{ ok: boolean }>(`/sessions/${sessionId}`)
}

export function clearAllSessions(userId: string): Promise<{ ok: boolean; deleted_count: number }> {
  return apiDelete<{ ok: boolean; deleted_count: number }>('/sessions', { user_id: userId })
}

export function updateSessionName(
  sessionId: string,
  sessionName: string,
): Promise<{ session_id: string; session_name: string; updated_at: string }> {
  return apiPut<{ session_id: string; session_name: string; updated_at: string }>(`/sessions/${sessionId}/name`, {
    session_name: sessionName,
  })
}
