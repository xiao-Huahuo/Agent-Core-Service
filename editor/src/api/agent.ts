/*
 * Agent streaming API.
 *
 * Usage:
 * The editor Agent panel calls streamPrompt() to consume the same backend SSE
 * chat endpoint as the console front-end.
 */

import { apiDelete, apiGet, apiPost, apiPostForm, apiPut, buildApiUrl, streamLines } from '@/api/client'
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
export type AgentAccessMode = 'readonly' | 'sandbox' | 'full_access'

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
  options: { signal?: AbortSignal; reference?: string; agentMode?: AgentLoopMode; agentAccessMode?: AgentAccessMode } = {},
): AsyncGenerator<Record<string, unknown>> {
  const body = {
    user_id: userId,
    session_id: sessionId,
    prompt,
    reference: options.reference?.trim() || undefined,
    agent_mode: options.agentMode || 'auto',
    agent_access_mode: options.agentAccessMode || 'sandbox',
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

export interface TaskSuggestionsResponse {
  suggestions: string[]
}

export function fetchTaskSuggestions(userId: string, sessionId: string): Promise<TaskSuggestionsResponse> {
  return apiPost<TaskSuggestionsResponse>(API_ROUTES.AGENT_TASK_SUGGESTIONS, {
    user_id: userId,
    session_id: sessionId,
  })
}

export type TokenUsageInterval =
  | '1m'
  | '3m'
  | '5m'
  | '10m'
  | '30m'
  | '1h'
  | '2h'
  | '3h'
  | '6h'
  | '12h'
  | '24h'
  | '3d'
  | '10d'
  | '15d'
  | 'month'

export interface TokenUsageCall {
  token_usage_id: string
  session_id: string
  message_id: string
  node: string
  event: string
  model_tier: 'large' | 'small'
  model_name: string
  input_tokens: number
  output_tokens: number
  total_tokens: number
  created_at: string
}

export interface TokenUsageBucket {
  bucket: string
  label: string
  start_at: string
  large_tokens: number
  small_tokens: number
  total_tokens: number
  call_count: number
}

export interface TokenUsageSessionTotal {
  session_id: string
  session_name: string
  large_tokens: number
  small_tokens: number
  total_tokens: number
  call_count: number
  updated_at: string
}

export interface TokenUsageStatsResponse {
  interval: TokenUsageInterval
  calls: TokenUsageCall[]
  buckets: TokenUsageBucket[]
  sessions: TokenUsageSessionTotal[]
}

export function fetchTokenUsageStats(
  userId: string,
  options: { sessionId?: string | null; interval?: TokenUsageInterval; limit?: number } = {},
): Promise<TokenUsageStatsResponse> {
  return apiGet<TokenUsageStatsResponse>(API_ROUTES.AGENT_TOKEN_USAGE, {
    user_id: userId,
    session_id: options.sessionId || undefined,
    interval: options.interval || '5m',
    limit: options.limit || 120,
  })
}
