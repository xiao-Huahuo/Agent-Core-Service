/*
 * LaTeX runtime and compilation API client.
 *
 * Usage:
 * Editor and storage settings use these functions for compiler detection,
 * managed MiKTeX lifecycle, and saved `.tex` compilation.
 */

import { apiGet, apiPost } from '@/api/client'
import { API_ROUTES } from '@/router/api_routes'
import type { FilePreviewPayload } from '@/types/knowledge'

/** Runtime states returned by the shared backend installer service. */
export type LatexRuntimeState = 'idle' | 'missing' | 'downloading' | 'installing' | 'cancelling' | 'failed' | 'ready'

/** One detected compiler or active managed-install state. */
export interface LatexRuntimeStatus {
  status: LatexRuntimeState
  stage: string
  progress: number | null
  downloaded_bytes?: number
  total_bytes?: number | null
  indeterminate?: boolean
  message: string
  source: 'managed' | 'system' | 'none'
  managed: boolean
  distribution?: string
  version?: string
  compiler_path?: string
  latexmk_path?: string
  /** Engine selected when the document has no `%!TeX program` declaration. */
  default_engine?: 'pdflatex' | 'xelatex' | 'lualatex' | ''
  runtime_path: string
}

/** One compiler engine discovered inside the active distribution. */
export interface LatexEngineDetail {
  name: 'pdflatex' | 'xelatex' | 'lualatex'
  available: boolean
  path: string
  default: boolean
}

/** Full compiler-management response used only by storage settings. */
export interface LatexManagementStatus extends LatexRuntimeStatus {
  distribution_path: string
  size_bytes: number
  file_count: number
  engines: LatexEngineDetail[]
  paths: Record<string, string>
}

/** One source-mapped LaTeX compiler diagnostic. */
export interface LatexCompileError {
  file: string
  line: number
  message: string
}

/** Compilation result consumed by the split PDF surface. */
export interface LatexCompileResult {
  success: boolean
  path: string
  root_path: string
  engine: 'pdflatex' | 'xelatex' | 'lualatex'
  output: string
  errors: LatexCompileError[]
  preview: FilePreviewPayload | null
}

/** Detect the active system or managed LaTeX toolchain. */
export function fetchLatexStatus(userId: string): Promise<LatexRuntimeStatus> {
  return apiGet(API_ROUTES.SETTINGS_LATEX_STATUS, { user_id: userId })
}

/** Load the detailed distribution, engine and disk state for compiler management. */
export function fetchLatexManagement(userId: string): Promise<LatexManagementStatus> {
  return apiGet(API_ROUTES.SETTINGS_LATEX_MANAGEMENT, { user_id: userId })
}

/** Begin the user-confirmed managed MiKTeX installation. */
export function installLatexRuntime(userId: string): Promise<LatexRuntimeStatus> {
  return apiPost(API_ROUTES.SETTINGS_LATEX_INSTALL, { user_id: userId })
}

/** Cancel an active managed MiKTeX download or setup process. */
export function cancelLatexInstall(userId: string): Promise<LatexRuntimeStatus> {
  return apiPost(API_ROUTES.SETTINGS_LATEX_INSTALL_CANCEL, { user_id: userId })
}

/** Remove only the MiKTeX runtime installed by MetaWeave. */
export function uninstallLatexRuntime(userId: string): Promise<LatexRuntimeStatus> {
  return apiPost(API_ROUTES.SETTINGS_LATEX_UNINSTALL, { user_id: userId })
}

/** Compile an already-saved `.tex` document and return its PDF preview. */
export function compileLatexFile(userId: string, path: string): Promise<LatexCompileResult> {
  return apiPost(API_ROUTES.KNOWLEDGE_LATEX_COMPILE, { user_id: userId, path }, { timeoutMs: 150_000 })
}
