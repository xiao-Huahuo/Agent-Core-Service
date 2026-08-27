/*
 * Favorite API client.
 *
 * Usage:
 * Components and stores call these helpers to persist user favorites through
 * the backend /favorites endpoints. This module never stores business data in
 * browser storage.
 */

import { apiDelete, apiGet, apiPost } from '@/api/client'
import { API_ROUTES } from '@/router/api_routes'

export type FavoriteTargetType = 'knowledge_path' | 'library_item' | 'component' | 'session' | 'smart_form_row'

export interface FavoriteRecord {
  favorite_id: string
  user_id: string
  library_id: string
  target_type: FavoriteTargetType
  target_id: string
  created_at: string
}

export interface FavoritePayload {
  user_id: string
  library_id?: string
  target_type: FavoriteTargetType
  target_id: string
}

export function listFavorites(params: {
  userId: string
  targetType?: FavoriteTargetType
  libraryId?: string | null
}): Promise<{ favorites: FavoriteRecord[] }> {
  return apiGet<{ favorites: FavoriteRecord[] }>(API_ROUTES.FAVORITES, {
    user_id: params.userId,
    target_type: params.targetType,
    library_id: params.libraryId,
  })
}

export function addFavorite(payload: FavoritePayload): Promise<FavoriteRecord> {
  return apiPost<FavoriteRecord>(API_ROUTES.FAVORITES, payload)
}

export function deleteFavorite(payload: FavoritePayload): Promise<{ ok: boolean; deleted: boolean }> {
  return apiDelete<{ ok: boolean; deleted: boolean }>(API_ROUTES.FAVORITES, {
    user_id: payload.user_id,
    library_id: payload.library_id ?? '',
    target_type: payload.target_type,
    target_id: payload.target_id,
  })
}
