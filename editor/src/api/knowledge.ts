/*
 * Editor knowledge file API.
 *
 * Usage:
 * Workspace stores call these helpers to load the backend file tree, read and
 * save text files, upload dropped files, and subscribe to file change events.
 */

import { apiDelete, apiGet, apiPost, apiPostForm, buildApiUrl } from '@/api/client'
import { API_ROUTES } from '@/router/api_routes'
import type { KnowledgeFileNode, SearchResults } from '@/types/knowledge'
import type { FilePreviewPayload } from '@/types/knowledge'

export interface KnowledgeTreeResponse {
  tree: KnowledgeFileNode[]
}

export interface KnowledgeFileContentResponse {
  path: string
  content: string
  mtime: string
  size: number
}

export interface KnowledgeFileEvent {
  type: 'ready' | 'tree_dirty'
  path: string
}

export function listKnowledgeFiles(userId: string): Promise<KnowledgeTreeResponse> {
  return apiGet<KnowledgeTreeResponse>(API_ROUTES.KNOWLEDGE_FILES, { user_id: userId })
}

export function readKnowledgeFile(userId: string, path: string): Promise<KnowledgeFileContentResponse> {
  return apiGet<KnowledgeFileContentResponse>(API_ROUTES.KNOWLEDGE_FILE_CONTENT, {
    user_id: userId,
    path,
  })
}

export function previewKnowledgeFile(userId: string, path: string): Promise<FilePreviewPayload> {
  return apiGet<FilePreviewPayload>(API_ROUTES.KNOWLEDGE_FILE_PREVIEW, {
    user_id: userId,
    path,
  })
}

export function writeKnowledgeFile(
  userId: string,
  path: string,
  content: string,
): Promise<KnowledgeFileNode> {
  return apiPost<KnowledgeFileNode>(API_ROUTES.KNOWLEDGE_FILE_CONTENT, {
    user_id: userId,
    path,
    content,
  })
}

export function uploadKnowledgeFile(
  userId: string,
  file: File,
  relativeDir = '',
): Promise<unknown> {
  const form = new FormData()
  form.set('user_id', userId)
  form.set('relative_dir', relativeDir)
  form.set('file', file)
  return apiPostForm(API_ROUTES.KNOWLEDGE_FILE_UPLOAD, form)
}

export function createKnowledgeFile(
  userId: string,
  path: string,
  content = '',
): Promise<KnowledgeFileNode> {
  return apiPost<KnowledgeFileNode>(API_ROUTES.KNOWLEDGE_FILE_CREATE, {
    user_id: userId,
    path,
    content,
  })
}

export function createKnowledgeFolder(userId: string, path: string): Promise<KnowledgeFileNode> {
  return apiPost<KnowledgeFileNode>(API_ROUTES.KNOWLEDGE_FILE_FOLDER, { user_id: userId, path })
}

export function copyKnowledgePath(
  userId: string,
  sourcePath: string,
  targetPath: string,
): Promise<KnowledgeFileNode> {
  return apiPost<KnowledgeFileNode>(API_ROUTES.KNOWLEDGE_FILE_COPY, {
    user_id: userId,
    source_path: sourcePath,
    target_path: targetPath,
  })
}

export function renameKnowledgePath(
  userId: string,
  sourcePath: string,
  targetPath: string,
): Promise<KnowledgeFileNode> {
  return apiPost<KnowledgeFileNode>(API_ROUTES.KNOWLEDGE_FILE_RENAME, {
    user_id: userId,
    source_path: sourcePath,
    target_path: targetPath,
  })
}

export function deleteKnowledgePath(userId: string, path: string): Promise<{ ok: boolean }> {
  const encodedUser = encodeURIComponent(userId)
  const encodedPath = encodeURIComponent(path)
  return apiDelete<{ ok: boolean }>(
    `${API_ROUTES.KNOWLEDGE_FILES}?user_id=${encodedUser}&path=${encodedPath}`,
  )
}

export function searchKnowledge(
  userId: string,
  query: string,
  fulltext = true,
  semantic = false,
): Promise<SearchResults> {
  return apiGet<SearchResults>(API_ROUTES.KNOWLEDGE_SEARCH, {
    user_id: userId,
    query,
    fulltext: fulltext ? 'true' : 'false',
    semantic: semantic ? 'true' : 'false',
  })
}

export function buildKnowledgeEventsUrl(userId: string): string {
  return buildApiUrl(API_ROUTES.KNOWLEDGE_FILE_EVENTS, { user_id: userId })
}
