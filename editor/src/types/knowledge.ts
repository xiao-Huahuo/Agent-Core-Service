/*
 * Shared knowledge editor domain types.
 *
 * Usage:
 * Keep file tree, editor, indexing, command, and chat DTOs here so Vue
 * components can stay focused on rendering and interaction.
 */

/** Index lifecycle shown in the file tree and top status bar. */
export type IndexStatus = 'clean' | 'dirty' | 'indexing' | 'indexed' | 'failed'

/** Editor display mode controlled by the central toolbar. */
export type EditorViewMode = 'edit' | 'preview' | 'split'

/** Main center workspace surface controlled by activity bar and commands. */
export type WorkspaceMainView = 'editor' | 'graph' | 'dashboard' | 'search' | 'settings'

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
