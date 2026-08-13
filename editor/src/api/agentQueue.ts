/**
 * Durable Agent task queue API.
 *
 * Usage:
 * The queue store and board use these functions exclusively; no queue state is
 * fabricated in the browser.
 */

import { apiDelete, apiGet, apiPost, apiPut } from '@/api/client'
import { API_ROUTES } from '@/router/api_routes'
import type { AgentUploadedAttachment } from '@/stores/chat'

export type AgentQueuePriority = 'critical' | 'high' | 'medium' | 'low' | 'whenever'
export type AgentQueueStatus = 'pending' | 'running' | 'review' | 'confirmed' | 'terminated'

export interface AgentQueueTask {
  task_id: string
  user_id: string
  prompt: string
  priority: AgentQueuePriority
  status: AgentQueueStatus
  session_id: string | null
  attachments: AgentUploadedAttachment[]
  started_at: string | null
  finished_at: string | null
  terminated_at: string | null
  created_at: string
  updated_at: string
  previous_task_id: string | null
  task_list?: { items?: Array<{ status: string }> } | null
}

export interface QueueTaskPayload {
  user_id: string
  prompt: string
  priority: AgentQueuePriority
  attachments: AgentUploadedAttachment[]
}

/** Load the live board or the confirmed/terminated history for one user. */
export function fetchQueue(userId: string, history = false) {
  return apiGet<{ tasks: AgentQueueTask[]; settings: { max_concurrency: number } }>(
    API_ROUTES.AGENT_QUEUE_TASKS,
    { user_id: userId, history },
  )
}

/** Persist a new independently executable Agent task. */
export function createQueueTask(payload: QueueTaskPayload & { session_id: string }) {
  return apiPost<AgentQueueTask>(API_ROUTES.AGENT_QUEUE_TASKS, payload)
}

/** Replace the editable fields of a pending task. */
export function updateQueueTask(taskId: string, payload: QueueTaskPayload) {
  return apiPut<AgentQueueTask>(API_ROUTES.AGENT_QUEUE_TASK(taskId), payload)
}

/** Transition a task to confirmed or terminated. */
export function transitionQueueTask(taskId: string, userId: string, status: 'confirmed' | 'terminated') {
  return apiPost<AgentQueueTask>(API_ROUTES.AGENT_QUEUE_TRANSITION(taskId), { user_id: userId, status })
}

/** Persist the per-user concurrent worker limit. */
export function updateQueueSettings(userId: string, maxConcurrency: number) {
  return apiPut<{ max_concurrency: number }>(API_ROUTES.AGENT_QUEUE_SETTINGS, {
    user_id: userId,
    max_concurrency: maxConcurrency,
  })
}

/** Delete an unclaimed task. */
export function deleteQueueTask(taskId: string, userId: string) {
  return apiDelete<{ deleted: boolean }>(API_ROUTES.AGENT_QUEUE_TASK(taskId), { user_id: userId })
}

/** Return a reviewed task to pending with a replacement prompt and attachments. */
export function continueQueueTask(taskId: string, payload: Pick<QueueTaskPayload, 'user_id' | 'prompt' | 'attachments'>) {
  return apiPost<AgentQueueTask>(API_ROUTES.AGENT_QUEUE_CONTINUE(taskId), payload)
}
