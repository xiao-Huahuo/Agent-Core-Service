/**
 * Component library API client.
 *
 * Usage:
 * Lists knowledge-directory component files by fixed tag and persists source
 * submitted by the live-preview upload form.
 */

import { apiDelete, apiGet, apiPatch, apiPost } from '@/api/client'
import { API_ROUTES } from '@/router/api_routes'
import type {
  ComponentLibraryCreatePayload,
  ComponentLibraryItem,
  ComponentLibraryResponse,
  ComponentLibraryRenamePayload,
  ComponentLibraryUpdatePayload,
  ComponentTag,
} from '@/types/componentLibrary'

/** List component cards for one user and sidebar tag. */
export function listComponentLibraryItems(
  userId: string,
  tag: ComponentTag = 'any',
): Promise<ComponentLibraryResponse> {
  return apiGet<ComponentLibraryResponse>(API_ROUTES.COMPONENT_LIBRARY_ITEMS, {
    user_id: userId,
    tag,
  })
}

/** Persist one source file, its original basename, and its only fixed tag. */
export function createComponentLibraryItem(
  payload: ComponentLibraryCreatePayload,
): Promise<{ component: ComponentLibraryItem }> {
  return apiPost<{ component: ComponentLibraryItem }>(API_ROUTES.COMPONENT_LIBRARY_ITEMS, payload)
}

/** Persist one inline title edit by renaming the canonical component file. */
export function renameComponentLibraryItem(
  userId: string,
  componentId: string,
  title: string,
): Promise<{ component: ComponentLibraryItem }> {
  const payload: ComponentLibraryRenamePayload = {
    user_id: userId,
    component_id: componentId,
    title,
  }
  return apiPatch<{ component: ComponentLibraryItem }>(API_ROUTES.COMPONENT_LIBRARY_ITEMS, payload)
}

/** Persist source, title, or tag changes without requiring unrelated fields. */
export function updateComponentLibraryItem(
  userId: string,
  componentId: string,
  changes: ComponentLibraryUpdatePayload,
): Promise<{ component: ComponentLibraryItem }> {
  return apiPatch<{ component: ComponentLibraryItem }>(API_ROUTES.COMPONENT_LIBRARY_ITEMS, {
    user_id: userId,
    component_id: componentId,
    ...changes,
  })
}

/** Delete one canonical component file from the active component library. */
export function deleteComponentLibraryItem(
  userId: string,
  componentId: string,
): Promise<{ component_id: string; deleted: boolean }> {
  return apiDelete<{ component_id: string; deleted: boolean }>(API_ROUTES.COMPONENT_LIBRARY_ITEMS, {
    user_id: userId,
    component_id: componentId,
  })
}
