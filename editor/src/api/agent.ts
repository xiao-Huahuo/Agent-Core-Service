/*
 * Agent streaming API.
 *
 * Usage:
 * The editor Agent panel calls streamPrompt() to consume the same backend SSE
 * chat endpoint as the console front-end.
 */

import { apiDelete, apiGet, apiPostForm, apiPut, buildApiUrl, streamLines } from '@/api/client'
import { API_ROUTES } from '@/router/api_routes'

export interface AgentStreamChunk {
  type?: string
  node?: string
  content?: string
  tool_calls?: unknown[]
  trace?: Array<Record<string, unknown>>
  metadata?: Record<string, unknown>
  context_messages?: unknown[]
}

export type AgentLoopMode = 'auto' | 'simple' | 'react' | 'plan'

export interface CurrentDocumentContextPayload {
  user_id: string
  path: string
  name: string
  knowledge_dir: string
  library_id: string
  library_name: string
  size?: number
  mtime?: string
  dirty: boolean
  open_tab_count: number
}

export function streamPrompt(
  userId: string,
  sessionId: string,
  prompt: string,
  options: { signal?: AbortSignal; reference?: string; agentMode?: AgentLoopMode } = {},
): AsyncGenerator<Record<string, unknown>> {
  const body = {
    user_id: userId,
    session_id: sessionId,
    prompt,
    reference: options.reference?.trim() || undefined,
    agent_mode: options.agentMode || 'auto',
  }
  return streamLines(
    buildApiUrl(API_ROUTES.AGENT_STREAM),
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: options.signal,
    },
  )
}

export function updateCurrentDocumentContext(payload: CurrentDocumentContextPayload): Promise<unknown> {
  return apiPut(API_ROUTES.AGENT_CURRENT_DOCUMENT_CONTEXT, payload)
}

export interface AgentAttachmentUploadResponse {
  ok: boolean
  attachment: {
    attachment_id: string
    user_id: string
    session_id: string
    library_id: string
    library_name: string
    filename: string
    stored_name: string
    uri: string
    mime_type: string
    size: number
    source_type: string
    summary?: string
    metadata?: Record<string, unknown>
    created_at: string
  }
}

export function uploadAgentAttachment(
  userId: string,
  sessionId: string,
  file: File,
): Promise<AgentAttachmentUploadResponse> {
  const form = new FormData()
  form.set('user_id', userId)
  form.set('session_id', sessionId)
  form.set('file', file)
  return apiPostForm<AgentAttachmentUploadResponse>(API_ROUTES.AGENT_ATTACHMENTS_UPLOAD, form, {
    timeoutMs: 600_000,
  })
}

export function deleteAgentAttachment(
  userId: string,
  sessionId: string,
  attachmentId: string,
): Promise<{ ok: boolean; deleted: boolean; attachment_id: string }> {
  return apiDelete(`${API_ROUTES.AGENT_ATTACHMENTS}/${encodeURIComponent(attachmentId)}`, {
    user_id: userId,
    session_id: sessionId,
  })
}

export interface RecallDetailsResponse {
  session_id: string
  user_id: string
  created_at: string
  query: string
  rag_metrics: Record<string, unknown>
  memory_recall: Record<string, unknown>
  knowledge_recall: Record<string, unknown>
}

export function fetchRecallDetails(sessionId: string, userId: string): Promise<RecallDetailsResponse> {
  return apiGet<RecallDetailsResponse>(API_ROUTES.AGENT_RECALL_DETAILS, { session_id: sessionId, user_id: userId })
}
