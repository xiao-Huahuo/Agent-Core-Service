/*
 * Smart forms API client.
 *
 * Usage:
 * SmartFormsView stores table schemas, rows, and cells through these database
 * endpoints. Uploaded document assets still use the knowledge-file API.
 */

import { apiDelete, apiGet, apiPost } from '@/api/client'
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

export interface StructuredGenerationField {
  id: string
  title: string
  type: 'text' | 'tag' | 'number' | 'boolean' | 'date'
  description?: string
  options?: string[]
  required?: boolean
}

export interface StructuredGenerationFieldResult {
  field_id: string
  status: 'ready' | 'failed'
  value: string
  error?: string
  raw_value?: unknown
}

export interface StructuredGenerationResponse {
  results: StructuredGenerationFieldResult[]
  raw_output: string
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

/** Permanently deletes one database-backed table owned by the current user. */
export function deleteSmartFormDb(userId: string, formId: string): Promise<void> {
  return apiDelete<void>(API_ROUTES.SMART_FORM_DETAIL(formId), { user_id: userId })
}

export function generateStructuredFields(payload: {
  user_id: string
  source: {
    kind: string
    content: string
    metadata?: Record<string, unknown>
  }
  fields: StructuredGenerationField[]
  options?: {
    language?: string
    strict_json?: boolean
  }
}): Promise<StructuredGenerationResponse> {
  return apiPost<StructuredGenerationResponse>(API_ROUTES.STRUCTURED_GENERATION_FIELDS, payload, { timeoutMs: 120_000 })
}
