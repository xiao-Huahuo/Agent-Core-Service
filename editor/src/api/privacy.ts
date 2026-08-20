/*
 * Privacy API client.
 *
 * Usage:
 * PrivacyStore calls these helpers to persist file and library-item privacy
 * through /privacy. No business state is stored in the browser.
 */

import { apiDelete, apiGet, apiPost } from '@/api/client'
import { API_ROUTES } from '@/router/api_routes'

export type PrivacyTargetType = 'knowledge_path' | 'library_item'

export interface PrivacyRecord {
  privacy_id: string
  user_id: string
  library_id: string
  target_type: PrivacyTargetType
  target_id: string
  created_at: string
}

export interface PrivacyPayload {
  user_id: string
  library_id?: string
  target_type: PrivacyTargetType
  target_id: string
}

export function listPrivacy(params: {
  userId: string
  targetType?: PrivacyTargetType
  libraryId?: string | null
}): Promise<{ privacy: PrivacyRecord[] }> {
  return apiGet(API_ROUTES.PRIVACY, {
    user_id: params.userId,
    target_type: params.targetType,
    library_id: params.libraryId,
  })
}

export function addPrivacy(payload: PrivacyPayload): Promise<PrivacyRecord> {
  return apiPost(API_ROUTES.PRIVACY, payload)
}

export function deletePrivacy(payload: PrivacyPayload): Promise<{ ok: boolean; deleted: boolean }> {
  return apiDelete(API_ROUTES.PRIVACY, {
    user_id: payload.user_id,
    library_id: payload.library_id ?? '',
    target_type: payload.target_type,
    target_id: payload.target_id,
  })
}
