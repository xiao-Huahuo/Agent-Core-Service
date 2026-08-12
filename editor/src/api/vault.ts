/*
 * Password vault API.
 *
 * Usage:
 * VaultView stores the returned vault token in sessionStorage for the 30-minute
 * unlock window and passes it in Authorization headers for every vault call.
 */

import { apiGet, apiPatch, apiPost, apiPostForm, buildApiUrl } from '@/api/client'
import { API_ROUTES } from '@/router/api_routes'

export type VaultItemType = 'login' | 'card' | 'identity' | 'secure_note'

export interface VaultTokenResponse {
  token: string
  scope: 'vault'
  expires_at: string
  user_id: string
}

export interface VaultStatusResponse {
  user_id: string
  configured: boolean
  item_count: number
}

export interface VaultDebugMasterPasswordResponse {
  user_id: string
  configured: boolean
  available: boolean
  master_password: string
  message: string
}

export interface VaultItem {
  item_id: string
  user_id: string
  item_type: VaultItemType
  name: string
  fields: Record<string, unknown>
  safe_fields: Record<string, unknown>
  tags: string[]
  deleted_at: string
  created_at: string
  updated_at: string
}

export interface VaultListResponse {
  items: VaultItem[]
  total: number
  type_counts: Record<VaultItemType, number>
}

export interface VaultTag {
  tag_id: string
  name: string
}

export interface VaultAsset {
  asset_id: string
  item_id: string
  mime_type: string
  file_name: string
  size: number
  created_at: string
}

function auth(token: string): RequestInit {
  return { headers: { Authorization: `Bearer ${token}` } }
}

export function getVaultStatus(userId: string): Promise<VaultStatusResponse> {
  return apiGet<VaultStatusResponse>(API_ROUTES.VAULT_STATUS, { user_id: userId })
}

export function getVaultDebugMasterPassword(userId: string): Promise<VaultDebugMasterPasswordResponse> {
  return apiGet<VaultDebugMasterPasswordResponse>(API_ROUTES.VAULT_DEBUG_MASTER_PASSWORD, { user_id: userId })
}

export function setupVault(userId: string, masterPassword: string): Promise<VaultTokenResponse> {
  return apiPost<VaultTokenResponse>(API_ROUTES.VAULT_SETUP, { user_id: userId, master_password: masterPassword })
}

export function unlockVault(userId: string, masterPassword: string): Promise<VaultTokenResponse> {
  return apiPost<VaultTokenResponse>(API_ROUTES.VAULT_UNLOCK, { user_id: userId, master_password: masterPassword })
}

export function resetVaultPassword(userId: string, newPassword: string, oldPassword = ''): Promise<{ ok: boolean }> {
  return apiPost<{ ok: boolean }>(API_ROUTES.VAULT_RESET_PASSWORD, { user_id: userId, new_password: newPassword, old_password: oldPassword })
}

export function lockVaultToken(token: string): Promise<{ ok: boolean }> {
  return apiPost<{ ok: boolean }>(API_ROUTES.VAULT_LOCK, {}, auth(token))
}

export function listVaultItems(
  token: string,
  params: { query?: string; tag?: string; itemType?: string; trash?: boolean },
): Promise<VaultListResponse> {
  return apiGet<VaultListResponse>(API_ROUTES.VAULT_ITEMS, {
    query: params.query ?? '',
    tag: params.tag ?? '',
    item_type: params.itemType ?? '',
    trash: params.trash ?? false,
  }, auth(token))
}

export function listVaultTags(token: string): Promise<{ tags: VaultTag[] }> {
  return apiGet<{ tags: VaultTag[] }>(API_ROUTES.VAULT_TAGS, {}, auth(token))
}

export function createVaultItem(
  token: string,
  payload: { item_type: VaultItemType; fields: Record<string, unknown>; tags: string[]; asset_ids?: string[] },
): Promise<{ item: VaultItem }> {
  return apiPost<{ item: VaultItem }>(API_ROUTES.VAULT_ITEMS, payload, auth(token))
}

export function getVaultItem(token: string, itemId: string): Promise<{ item: VaultItem }> {
  return apiGet<{ item: VaultItem }>(`${API_ROUTES.VAULT_ITEMS}/${encodeURIComponent(itemId)}`, {}, auth(token))
}

export function updateVaultItem(
  token: string,
  itemId: string,
  payload: { item_type?: VaultItemType; fields?: Record<string, unknown>; tags?: string[]; asset_ids?: string[] },
): Promise<{ item: VaultItem }> {
  return apiPatch<{ item: VaultItem }>(`${API_ROUTES.VAULT_ITEMS}/${encodeURIComponent(itemId)}`, payload, auth(token))
}

export function trashVaultItems(token: string, itemIds: string[]): Promise<{ ok: boolean; changed_count: number }> {
  return apiPost<{ ok: boolean; changed_count: number }>(API_ROUTES.VAULT_ITEM_TRASH, { item_ids: itemIds }, auth(token))
}

export function restoreVaultItems(token: string, itemIds: string[]): Promise<{ ok: boolean; changed_count: number }> {
  return apiPost<{ ok: boolean; changed_count: number }>(API_ROUTES.VAULT_ITEM_RESTORE, { item_ids: itemIds }, auth(token))
}

export function purgeVaultItems(token: string, itemIds: string[]): Promise<{ ok: boolean; deleted_count: number }> {
  return apiPost<{ ok: boolean; deleted_count: number }>(API_ROUTES.VAULT_ITEM_PURGE, { item_ids: itemIds }, auth(token))
}

export function exportVaultItems(token: string, itemIds?: string[]): Promise<Record<string, unknown>> {
  return apiPost<Record<string, unknown>>(API_ROUTES.VAULT_EXPORT, { item_ids: itemIds ?? [] }, auth(token))
}

export function importVaultItems(token: string, items: Record<string, unknown>[]): Promise<{ imported: number; converted_to_secure_note: number; failed: number }> {
  return apiPost<{ imported: number; converted_to_secure_note: number; failed: number }>(API_ROUTES.VAULT_IMPORT, { items }, auth(token))
}

export function uploadVaultAsset(token: string, file: File): Promise<{ asset: VaultAsset }> {
  const form = new FormData()
  form.set('file', file)
  return apiPostForm<{ asset: VaultAsset }>(API_ROUTES.VAULT_ASSETS, form, auth(token))
}

export async function fetchVaultAssetUrl(token: string, assetId: string): Promise<string> {
  const response = await fetch(buildApiUrl(`${API_ROUTES.VAULT_ASSETS}/${encodeURIComponent(assetId)}`), {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!response.ok) {
    throw new Error(`Vault asset request failed: ${response.status}`)
  }
  return URL.createObjectURL(await response.blob())
}
