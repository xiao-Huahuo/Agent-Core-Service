/*
 * User feedback API client.
 *
 * Usage:
 * Components submit user feedback through the backend /feedback endpoint. This
 * module does not persist drafts or feedback in browser storage.
 */

import { apiDelete, apiGet, apiPost, apiPut } from '@/api/client'
import { API_ROUTES } from '@/router/api_routes'

export interface FeedbackPayload {
  user_id: string
  content: string
  source?: string
  page?: string
}

export interface FeedbackRecord {
  feedback_id: string
  user_id: string
  content: string
  source: string
  page: string
  created_at: string
}

export interface FeedbackListResponse {
  feedback: FeedbackRecord[]
}

export interface FeedbackDeleteResponse {
  ok: boolean
  deleted_count: number
}

export function submitFeedback(payload: FeedbackPayload): Promise<FeedbackRecord> {
  return apiPost<FeedbackRecord>(API_ROUTES.FEEDBACK, payload)
}

export async function listFeedback(userId?: string): Promise<FeedbackRecord[]> {
  const normalizedUserId = userId?.trim()
  const response = await apiGet<FeedbackListResponse>(
    API_ROUTES.FEEDBACK,
    normalizedUserId ? { user_id: normalizedUserId } : undefined,
  )
  return response.feedback
}

export function updateFeedback(feedbackId: string, content: string): Promise<FeedbackRecord> {
  return apiPut<FeedbackRecord>(`${API_ROUTES.FEEDBACK}/${encodeURIComponent(feedbackId)}`, { content })
}

export function deleteFeedback(feedbackId: string): Promise<FeedbackDeleteResponse> {
  return apiDelete<FeedbackDeleteResponse>(`${API_ROUTES.FEEDBACK}/${encodeURIComponent(feedbackId)}`)
}
