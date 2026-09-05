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

export interface KnowledgeIngestionJob {
  job_id: string
  user_id: string
  library_id: string
  path: string
  name: string
  pipeline: string
  status: 'queued' | 'running' | 'cancelling' | 'cancelled' | 'finished' | 'skipped' | 'failed'
  stage: string
  stage_label: string
  progress: number
  stage_current: number
  stage_total: number
  size?: number
  mtime?: string
  message: string
  error: string
  created_at: string
  started_at?: string
  finished_at?: string
  updated_at: string
}

export function createKnowledgeIngestionJobs(userId: string, paths: string[]): Promise<{ jobs: KnowledgeIngestionJob[] }> {
  return apiPost(API_ROUTES.KNOWLEDGE_INGESTION_JOBS, { user_id: userId, paths })
}

export function listKnowledgeIngestionJobs(
  userId: string,
  activeOnly = false,
): Promise<{ jobs: KnowledgeIngestionJob[] }> {
  return apiGet(API_ROUTES.KNOWLEDGE_INGESTION_JOBS, {
    user_id: userId,
    active_only: activeOnly ? 'true' : 'false',
  })
}

export function cancelKnowledgeIngestionJob(userId: string, jobId: string): Promise<KnowledgeIngestionJob> {
  return apiPost(`${API_ROUTES.KNOWLEDGE_INGESTION_JOBS}/${encodeURIComponent(jobId)}/cancel`, {
    user_id: userId,
  })
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

export interface KnowledgeGraphMutationResult {
  ok: boolean
  deleted_nodes: number
  deleted_edges: number
}

/** Delete one persisted entity node together with every incident edge. */
export function deleteKnowledgeGraphNode(userId: string, nodeId: string): Promise<KnowledgeGraphMutationResult> {
  return apiDelete<KnowledgeGraphMutationResult>(
    `${API_ROUTES.KNOWLEDGE_GRAPH_NODES}/${encodeURIComponent(nodeId)}?user_id=${encodeURIComponent(userId)}`,
  )
}

/** Clear one document's contributed entity graph while preserving its document node. */
export function clearKnowledgeGraphDocument(userId: string, nodeId: string): Promise<KnowledgeGraphMutationResult> {
  return apiPost<KnowledgeGraphMutationResult>(
    `${API_ROUTES.KNOWLEDGE_GRAPH_NODES}/${encodeURIComponent(nodeId)}/clear`,
    { user_id: userId },
  )
}

export interface GraphDocStatus {
  path: string
  name: string
  status: 'pending' | 'processing' | 'cancelling' | 'cancelled' | 'done' | 'skipped' | 'failed'
  progress?: number
  total_sections?: number
  stage?: string
  stage_label?: string
  stage_current?: number
  stage_total?: number
  message?: string
}

export interface GraphRebuildStatus {
  status: 'idle' | 'running' | 'cancelled' | 'completed' | 'failed'
  total: number
  current: number
  message: string
  result?: Record<string, unknown> | null
  docs?: GraphDocStatus[]
}

export function rebuildKnowledgeGraph(userId: string, path?: string, force = false): Promise<{ status: string; message: string }> {
  return apiPost(API_ROUTES.KNOWLEDGE_GRAPH_REBUILD, { user_id: userId, path, force })
}

/** Cancel one queued or running graph extraction task by its knowledge-root-relative path. */
export function cancelKnowledgeGraphTask(userId: string, path: string): Promise<{ status: string; message: string }> {
  return apiPost(API_ROUTES.KNOWLEDGE_GRAPH_REBUILD_CANCEL, { user_id: userId, path })
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
