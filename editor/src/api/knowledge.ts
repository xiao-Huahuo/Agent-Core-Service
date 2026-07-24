/*
 * Editor knowledge file API.
 *
 * Usage:
 * Workspace stores call these helpers to load the backend file tree, read and
 * save text files, upload dropped files, and subscribe to file change events.
 */

import { apiDelete, apiGet, apiPost, apiPostForm, buildApiUrl, streamLines } from '@/api/client'
import { API_ROUTES } from '@/router/api_routes'
import type { KnowledgeFileNode, KnowledgeSemanticGraphResponse, KnowledgeTrashEntry, SearchResults } from '@/types/knowledge'
import type { FilePreviewPayload } from '@/types/knowledge'
import type { KnowledgeIngestionProgressEvent, KnowledgeRebuildResponse } from '@/api/settings'

export interface KnowledgeTreeResponse {
  tree: KnowledgeFileNode[]
}

export interface KnowledgeTrashResponse {
  entries: KnowledgeTrashEntry[]
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

export function previewKnowledgeFile(userId: string, path: string, signal?: AbortSignal): Promise<FilePreviewPayload> {
  return apiGet<FilePreviewPayload>(API_ROUTES.KNOWLEDGE_FILE_PREVIEW, {
    user_id: userId,
    path,
  }, { signal })
}

export function readKnowledgeFile(userId: string, path: string, signal?: AbortSignal): Promise<KnowledgeFileContentResponse> {
  return apiGet<KnowledgeFileContentResponse>(API_ROUTES.KNOWLEDGE_FILE_CONTENT, {
    user_id: userId,
    path,
  }, { signal })
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
  autoIngest?: boolean,
  conflictStrategy: 'overwrite' | 'skip' | 'rename' = 'overwrite',
): Promise<unknown> {
  const form = new FormData()
  form.set('user_id', userId)
  form.set('relative_dir', relativeDir)
  form.set('file', file)
  if (autoIngest !== undefined) {
    form.set('auto_ingest', autoIngest ? 'true' : 'false')
  }
  form.set('conflict_strategy', conflictStrategy)
  return apiPostForm(API_ROUTES.KNOWLEDGE_FILE_UPLOAD, form)
}

export function ingestKnowledgeFile(userId: string, path: string): Promise<unknown> {
  return apiPost(API_ROUTES.KNOWLEDGE_FILE_INGEST, {
    user_id: userId,
    path,
  }, {
    timeoutMs: 600_000,
  })
}

export function ingestKnowledgePath(userId: string, path: string): Promise<unknown> {
  return apiPost(API_ROUTES.KNOWLEDGE_FILE_INGEST_PATH, {
    user_id: userId,
    path,
  }, {
    timeoutMs: 600_000,
  })
}

async function streamIngestion(
  route: string,
  userId: string,
  path: string,
  onProgress: (event: KnowledgeIngestionProgressEvent) => void,
): Promise<KnowledgeRebuildResponse> {
  let finalResult: KnowledgeRebuildResponse | null = null
  for await (const event of streamLines(buildApiUrl(route), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId, path }),
  })) {
    const typed = event as KnowledgeIngestionProgressEvent
    if (typed.type === 'error') {
      throw new Error(typed.message || 'Knowledge ingestion failed')
    }
    if (typed.type === 'done' && typed.result) {
      finalResult = typed.result
    }
    onProgress(typed)
  }
  if (!finalResult) {
    throw new Error('Knowledge ingestion stream finished without a result')
  }
  return finalResult
}

export function ingestKnowledgeFileStream(
  userId: string,
  path: string,
  onProgress: (event: KnowledgeIngestionProgressEvent) => void,
): Promise<KnowledgeRebuildResponse> {
  return streamIngestion(API_ROUTES.KNOWLEDGE_FILE_INGEST_STREAM, userId, path, onProgress)
}

export function ingestKnowledgePathStream(
  userId: string,
  path: string,
  onProgress: (event: KnowledgeIngestionProgressEvent) => void,
): Promise<KnowledgeRebuildResponse> {
  return streamIngestion(API_ROUTES.KNOWLEDGE_FILE_INGEST_PATH_STREAM, userId, path, onProgress)
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

export function deleteKnowledgePath(userId: string, path: string): Promise<{ ok: boolean; trash_id?: string }> {
  const encodedUser = encodeURIComponent(userId)
  const encodedPath = encodeURIComponent(path)
  return apiDelete<{ ok: boolean; trash_id?: string }>(
    `${API_ROUTES.KNOWLEDGE_FILES}?user_id=${encodedUser}&path=${encodedPath}`,
  )
}

export function listKnowledgeTrash(userId: string): Promise<KnowledgeTrashResponse> {
  return apiGet<KnowledgeTrashResponse>(API_ROUTES.KNOWLEDGE_FILE_TRASH, { user_id: userId })
}

export function restoreKnowledgeTrashEntry(
  userId: string,
  trashId: string,
): Promise<{ ok: boolean; restored_path: string; node: KnowledgeFileNode }> {
  return apiPost(`${API_ROUTES.KNOWLEDGE_FILE_TRASH}/${encodeURIComponent(trashId)}/restore`, {
    user_id: userId,
  })
}

export function deleteKnowledgeTrashEntry(userId: string, trashId: string): Promise<{ ok: boolean }> {
  return apiDelete<{ ok: boolean }>(
    `${API_ROUTES.KNOWLEDGE_FILE_TRASH}/${encodeURIComponent(trashId)}?user_id=${encodeURIComponent(userId)}`,
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

export function fetchKnowledgeGraph(userId: string, limit = 2000): Promise<KnowledgeSemanticGraphResponse> {
  return apiGet<KnowledgeSemanticGraphResponse>(API_ROUTES.KNOWLEDGE_GRAPH, {
    user_id: userId,
    limit,
  })
}

export interface GraphDocStatus {
  path: string
  name: string
  status: 'pending' | 'processing' | 'done' | 'skipped' | 'failed'
  progress?: number
  total_sections?: number
}

export interface GraphRebuildStatus {
  status: 'idle' | 'running' | 'completed' | 'failed'
  total: number
  current: number
  message: string
  result?: Record<string, unknown> | null
  docs?: GraphDocStatus[]
}

export function rebuildKnowledgeGraph(userId: string, path?: string): Promise<{ status: string; message: string }> {
  return apiPost(API_ROUTES.KNOWLEDGE_GRAPH_REBUILD, { user_id: userId, path })
}

export interface DedupStatus {
  status: 'idle' | 'pending' | 'running' | 'completed' | 'failed'
  total: number
  current: number
  message: string
  merged_count: number
}

export function deduplicateKnowledgeGraph(userId: string): Promise<{ status: string; message: string }> {
  return apiPost(API_ROUTES.KNOWLEDGE_GRAPH_DEDUP, { user_id: userId })
}

export function getDedupStatus(userId: string): Promise<DedupStatus> {
  return apiGet<DedupStatus>(API_ROUTES.KNOWLEDGE_GRAPH_DEDUP_STATUS, { user_id: userId })
}

export function getKnowledgeGraphStatus(userId: string): Promise<GraphRebuildStatus> {
  return apiGet<GraphRebuildStatus>(API_ROUTES.KNOWLEDGE_GRAPH_REBUILD_STATUS, { user_id: userId })
}

export function buildKnowledgeEventsUrl(userId: string): string {
  return buildApiUrl(API_ROUTES.KNOWLEDGE_FILE_EVENTS, { user_id: userId })
}
