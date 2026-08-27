/*
 * Literature reading API client.
 *
 * Usage:
 * LiteratureReadingView loads smart-form row summaries, records visits, and
 * performs row-level mutations without overwriting unrelated table rows.
 */

import { apiDelete, apiGet, apiPatch, apiPost } from '@/api/client'
import type { SmartFormResponse } from '@/api/smartForms'
import { API_ROUTES } from '@/router/api_routes'

export interface LiteratureEntry {
  form_id: string
  form_title: string
  row_id: string
  title: string
  file_name: string
  asset_path: string
  content_excerpt: string
  file_size: number
  entered_at: string
  updated_at: string
  last_viewed_at: string
  tags: string[]
  rating: number
}

export function listLiteratureEntries(userId: string, libraryId: string): Promise<LiteratureEntry[]> {
  return apiGet<LiteratureEntry[]>(API_ROUTES.LITERATURE_READING_ENTRIES, {
    user_id: userId,
    library_id: libraryId,
  })
}

export function touchLiteratureEntry(userId: string, libraryId: string, formId: string, rowId: string): Promise<{ last_viewed_at: string }> {
  return apiPost(API_ROUTES.LITERATURE_READING_VIEW(formId, rowId), {
    user_id: userId,
    library_id: libraryId,
  })
}

export function patchLiteratureRow(userId: string, formId: string, rowId: string, cells: Record<string, unknown>): Promise<SmartFormResponse> {
  return apiPatch(API_ROUTES.LITERATURE_READING_ROW(formId, rowId), { user_id: userId, cells })
}

export function duplicateLiteratureRow(userId: string, formId: string, rowId: string): Promise<SmartFormResponse> {
  return apiPost(API_ROUTES.LITERATURE_READING_DUPLICATE(formId, rowId), { user_id: userId })
}

export function deleteLiteratureRow(userId: string, formId: string, rowId: string, deleteFile = true): Promise<void> {
  return apiDelete(API_ROUTES.LITERATURE_READING_ROW(formId, rowId), {
    user_id: userId,
    delete_file: deleteFile,
  })
}
