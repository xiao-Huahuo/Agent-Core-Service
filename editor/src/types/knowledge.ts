/*
 * Shared knowledge editor domain types.
 *
 * Usage:
 * Keep file tree, editor, indexing, command, and chat DTOs here so Vue
 * components can stay focused on rendering and interaction.
 */

/** Index lifecycle shown in the file tree and top status bar. */
export type IndexStatus = 'clean' | 'dirty' | 'indexing' | 'indexed' | 'failed' | 'ignored'

/** Editor display mode controlled by the central toolbar. */
export type EditorViewMode = 'edit' | 'preview' | 'split'

/** File viewer selected by extension and backend preview metadata. */
export type FileViewerKind = 'markdown' | 'code' | 'image' | 'pdf' | 'table' | 'document' | 'text' | 'unsupported'

/** Main center workspace surface controlled by activity bar and commands. */
export type WorkspaceMainView = 'editor' | 'resources' | 'graph' | 'dashboard' | 'search' | 'settings' | 'agent'

/** One file or directory in the knowledge tree. */
export interface KnowledgeFileNode {
  /** Display name shown in the recursive tree. */
  name: string
  /** Path relative to the configured knowledge root. */
  path: string
  /** Whether this node is a directory. */
  isDir: boolean
  /** Optional child nodes, loaded eagerly in the mock front-end. */
  children?: KnowledgeFileNode[]
  /** File size in bytes, if known. */
  size?: number
  /** Last modified timestamp in display-ready form. */
  mtime?: string
  /** Current indexing state for this file or directory. */
  indexStatus?: IndexStatus
}

/** Runtime events expected from the future watchdog/SSE endpoint. */
export type KnowledgeEvent =
  | { type: 'tree_dirty'; path: string }
  | { type: 'file_changed'; path: string; isDir: boolean }
  | { type: 'file_deleted'; path: string }
  | { type: 'index_status'; path: string; status: IndexStatus }

/** Open editor tab state. */
export interface EditorTab {
  /** File path relative to the knowledge root. */
  path: string
  /** File label used in the tab strip. */
  title: string
  /** Whether local editor content differs from saved content. */
  dirty: boolean
  /** Last known mtime from disk, used to detect external changes. */
  mtime?: string
}

/** One sheet used by CSV/XLSX previews. */
export interface TablePreviewSheet {
  /** Human-readable sheet name. */
  name: string
  /** Rectangular-ish table rows loaded from the backend. */
  rows: string[][]
}

/** Backend-generated multimodal preview payload. */
export interface FilePreviewPayload {
  /** File path relative to knowledge root. */
  path: string
  /** Viewer kind selected by backend. */
  kind: FileViewerKind
  /** Optional UTF-8 text content for generic text previews. */
  content?: string
  /** Optional sanitized-at-render HTML for DOCX previews. */
  html?: string
  /** Optional data URL for image/PDF embeds. */
  data_url?: string
  /** Optional backend raw file URL for iframe/object previews. */
  raw_url?: string
  /** Optional MIME type for binary embeds. */
  mime_type?: string
  /** Optional table sheets for CSV/XLSX previews. */
  sheets?: TablePreviewSheet[]
  /** Optional unsupported-file message. */
  message?: string
  /** Whether a PDF appears to have no extractable text layer. */
  pdf_scanned?: boolean
  /** Optional PDF page count from the backend parser. */
  page_count?: number
  /** Optional count of images detected in a PDF or document. */
  image_count?: number
  /** Optional count of tables detected in a PDF or document. */
  table_count?: number
  /** Optional OCR lifecycle for image previews. */
  ocr_status?: 'disabled' | 'completed' | 'no_text' | 'pending' | string
  /** Optional count of OCR words accepted by the backend. */
  ocr_word_count?: number
  /** Optional average OCR confidence for accepted words. */
  ocr_average_confidence?: number
  /** Whether OCR engine was available when preview was generated. */
  ocr_engine_available?: boolean
  /** Last modified timestamp from disk. */
  mtime: string
  /** File size in bytes. */
  size: number
  /** File extension including dot. */
  extension: string
  /** Whether this viewer should be treated as read-only. */
  readonly: boolean
}

/** Minimal chat message used by the right-side Agent panel. */
export interface ChatMessage {
  /** Stable id for Vue list rendering. */
  id: string
  /** Message author role. */
  role: 'user' | 'assistant' | 'system'
  /** Message body. */
  content: string
  /** Optional source path associated with the message. */
  sourcePath?: string
  /** Optional reference text quoted by the user. */
  reference?: string
}

/** Command palette action model. */
export interface CommandAction {
  /** Stable command id. */
  id: string
  /** Human-readable label. */
  label: string
  /** Keyboard shortcut hint. */
  shortcut?: string
  /** Short description shown below the label. */
  description: string
}

export interface FilenameResult {
  path: string
  name: string
}

export interface FulltextResult {
  source_uri: string
  snippet: string
}

export interface SearchResults {
  filename_results: FilenameResult[]
  fulltext_results: FulltextResult[]
  semantic_results: Record<string, unknown>[]
}

export interface KnowledgeSemanticGraphNode {
  id: string
  label: string
  kind: 'document' | 'entity' | string
  entity_type?: string
  document_id?: string
  source_uri?: string
  source_range?: Record<string, unknown>
  metadata?: Record<string, unknown>
}

export interface KnowledgeSemanticGraphLink {
  id: string
  source: string
  target: string
  kind: string
  weight?: number
  evidence?: string
  source_document_id?: string
  source_section_id?: string
  metadata?: Record<string, unknown>
}

export interface KnowledgeSemanticGraphResponse {
  nodes: KnowledgeSemanticGraphNode[]
  links: KnowledgeSemanticGraphLink[]
  stats: Record<string, number>
}
