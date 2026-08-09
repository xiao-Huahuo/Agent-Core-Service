/*
 * Smart forms API client.
 *
 * Usage:
 * SmartFormsView stores table schemas, rows, and cells through these database
 * endpoints. Uploaded document assets still use the knowledge-file API.
 */

import { apiGet, apiPost } from '@/api/client'
import { API_ROUTES } from '@/router/api_routes'
import type { SmartLiteratureForm } from '@/components/smart_forms/smartLiteratureTable'

export interface SmartFormListItem {
  form_id: string
  title: string
  asset_dir: string
  updated_at: string
}

export interface SmartFormResponse {
  form_id: string
  user_id: string
  asset_dir: string
  form: SmartLiteratureForm
  updated_at: string
}

export function listSmartFormsDb(userId: string): Promise<SmartFormListItem[]> {
  return apiGet<SmartFormListItem[]>(API_ROUTES.SMART_FORMS_LIST, { user_id: userId })
}

export function getSmartFormDb(userId: string, formId: string): Promise<SmartFormResponse> {
  return apiGet<SmartFormResponse>(API_ROUTES.SMART_FORM_DETAIL(formId), { user_id: userId })
}

export function saveSmartFormDb(payload: {
  user_id: string
  form_id?: string
  asset_dir: string
  form: SmartLiteratureForm
}): Promise<SmartFormResponse> {
  return apiPost<SmartFormResponse>(API_ROUTES.SMART_FORMS_SAVE, payload)
}
