import type { EditorWorkspaceMode, FileViewerKind } from '@/types/knowledge'

export interface EditorModeOption {
  mode: EditorWorkspaceMode
  label: string
  icon: string
}

export interface EditorFilePipeline {
  modes: EditorModeOption[]
  defaultMode: EditorWorkspaceMode
  usesPreviewEndpoint: boolean
  editable: boolean
}

const MARKDOWN_EXTENSIONS = new Set(['md', 'markdown'])
const TEXT_EXTENSIONS = new Set(['txt'])
const CODE_EXTENSIONS = new Set([
  'bash', 'c', 'cpp', 'cs', 'css', 'go', 'h', 'hpp', 'html', 'java', 'js', 'json',
  'jsx', 'kt', 'kts', 'php', 'py', 'rs', 'sh', 'sql', 'ts', 'tsx', 'vue', 'xml',
  'yaml', 'yml',
])
const IMAGE_EXTENSIONS = new Set(['gif', 'jpeg', 'jpg', 'png', 'svg', 'webp'])

const option = (mode: EditorWorkspaceMode, label: string, icon: string): EditorModeOption => ({ mode, label, icon })
const EDIT = option('edit', 'Edit', 'edit')
const PREVIEW = option('preview', 'Preview', 'visibility')
const SPLIT = option('split', 'Split', 'view-column')
const TEXT = option('text', 'Text', 'document')
const FORMS = option('forms', 'Forms', 'table-chart')
const MARKDOWN = option('markdown', 'Markdown', 'edit-note')
const CODE = option('code', 'Code', 'code')
const BINARY = option('binary', 'Binary', 'file')

export function extensionOfEditorPath(path: string): string {
  const name = path.replace(/\\/g, '/').split('/').pop()?.toLowerCase() ?? ''
  const dotIndex = name.lastIndexOf('.')
  return dotIndex >= 0 ? name.slice(dotIndex + 1) : ''
}

/** Returns the single editor contract used by loading, mode controls, and rendering. */
export function resolveEditorFilePipeline(path: string, backendKind?: FileViewerKind): EditorFilePipeline {
  const extension = extensionOfEditorPath(path)
  if (MARKDOWN_EXTENSIONS.has(extension)) {
    return { modes: [EDIT, PREVIEW, SPLIT], defaultMode: 'edit', usesPreviewEndpoint: false, editable: true }
  }
  if (TEXT_EXTENSIONS.has(extension)) {
    return { modes: [TEXT], defaultMode: 'text', usesPreviewEndpoint: false, editable: true }
  }
  if (CODE_EXTENSIONS.has(extension)) {
    return { modes: [CODE], defaultMode: 'code', usesPreviewEndpoint: false, editable: true }
  }
  if (extension === 'csv') {
    return { modes: [TEXT, FORMS], defaultMode: 'text', usesPreviewEndpoint: true, editable: true }
  }
  if (extension === 'xls' || extension === 'xlsx') {
    return { modes: [FORMS], defaultMode: 'forms', usesPreviewEndpoint: true, editable: false }
  }
  if (extension === 'docx' || extension === 'pdf' || extension === 'pptx' || IMAGE_EXTENSIONS.has(extension)) {
    return { modes: [PREVIEW, MARKDOWN], defaultMode: 'preview', usesPreviewEndpoint: true, editable: false }
  }
  if (backendKind === 'text') {
    return { modes: [TEXT], defaultMode: 'text', usesPreviewEndpoint: true, editable: true }
  }
  return { modes: [BINARY], defaultMode: 'binary', usesPreviewEndpoint: true, editable: false }
}
