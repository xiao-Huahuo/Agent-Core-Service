/*
 * Virtual library API.
 *
 * Usage:
 * LibraryView calls these helpers to manage user-curated virtual books,
 * collections, tags, and cover assets. Real files remain managed by
 * the knowledge-file API.
 */

import { apiDelete, apiGet, apiPatch, apiPost, apiPostForm } from '@/api/client'
import { API_ROUTES } from '@/router/api_routes'
import type { LibraryItem, LibraryItemsResponse, LibraryTag } from '@/types/knowledge'

export interface LibraryListParams {
  userId: string
  parentId?: string
  query?: string
  tag?: string
  contentType?: string
  sort?: string
  direction?: 'asc' | 'desc'
}

export interface LibraryItemPayload {
  user_id: string
  parent_id?: string
  content_type?: 'knowledge_file' | 'web_url' | 'external_file'
  source_path?: string
  source_url?: string
  title?: string
  description?: string
  cover_mode?: 'icon' | 'image' | 'description' | 'source_image' | 'title'
  cover_asset_id?: string
  sort_order?: number
  tags?: string[]
}

export function listLibraryItems(params: LibraryListParams): Promise<LibraryItemsResponse> {
  return apiGet<LibraryItemsResponse>(API_ROUTES.LIBRARY_ITEMS, {
    user_id: params.userId,
    parent_id: params.parentId ?? '',
    query: params.query ?? '',
    tag: params.tag ?? '',
    content_type: params.contentType ?? '',
    sort: params.sort ?? 'updated_at',
    direction: params.direction ?? 'desc',
  })
}

export function listLibraryTags(userId: string): Promise<{ tags: LibraryTag[] }> {
  return apiGet<{ tags: LibraryTag[] }>(API_ROUTES.LIBRARY_TAGS, { user_id: userId })
}

export function createLibraryBook(payload: LibraryItemPayload): Promise<{ item: LibraryItem }> {
  return apiPost<{ item: LibraryItem }>(API_ROUTES.LIBRARY_ITEM_BOOK, payload)
}

export function createLibraryCollection(payload: LibraryItemPayload): Promise<{ item: LibraryItem }> {
  return apiPost<{ item: LibraryItem }>(API_ROUTES.LIBRARY_ITEM_COLLECTION, payload)
}

export function updateLibraryItem(itemId: string, payload: LibraryItemPayload): Promise<{ item: LibraryItem }> {
  return apiPatch<{ item: LibraryItem }>(`${API_ROUTES.LIBRARY_ITEMS}/${encodeURIComponent(itemId)}`, payload)
}

export function deleteLibraryItem(userId: string, itemId: string): Promise<{ ok: boolean; deleted_item_ids: string[] }> {
  return apiDelete<{ ok: boolean; deleted_item_ids: string[] }>(
    `${API_ROUTES.LIBRARY_ITEMS}/${encodeURIComponent(itemId)}`,
    { user_id: userId },
  )
}

export function uploadLibraryCover(userId: string, file: File): Promise<{ asset: LibraryItem['cover_asset'] }> {
  const form = new FormData()
  form.set('user_id', userId)
  form.set('file', file)
  return apiPostForm<{ asset: LibraryItem['cover_asset'] }>(API_ROUTES.LIBRARY_COVER_UPLOAD, form)
}
