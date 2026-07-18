/*
 * File resource manager utility functions.
 *
 * Usage:
 * Pure path, date, file-kind, and size helpers used by FileResourceManager.vue.
 * Keep browser/store state out of this module so the component can own behavior.
 */

import type { KnowledgeFileNode } from '@/types/knowledge'

export function normalizeTreePath(path: string): string {
  return path.replace(/\\/g, '/').replace(/^\/+|\/+$/g, '')
}

export function parentPath(path: string): string {
  const parts = normalizeTreePath(path).split('/').filter(Boolean)
  parts.pop()
  return parts.join('/')
}

export function timestampOf(value?: string): number {
  if (!value || value === '-') {
    return 0
  }
  const parsed = Date.parse(value.replace(' ', 'T'))
  return Number.isNaN(parsed) ? 0 : parsed
}

export function extensionOf(name: string): string {
  const dotIndex = name.lastIndexOf('.')
  return dotIndex > -1 ? name.slice(dotIndex + 1).toLowerCase() : ''
}

export function isImageNode(node: KnowledgeFileNode): boolean {
  return !node.isDir && ['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'].includes(extensionOf(node.name))
}

export function fileKind(node: KnowledgeFileNode): string {
  if (node.isDir) return '文件夹'
  const ext = extensionOf(node.name)
  if (!ext) return '文件'
  if (['md', 'markdown'].includes(ext)) return 'Markdown'
  if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'].includes(ext)) return '图片'
  if (['csv', 'xls', 'xlsx', 'tsv'].includes(ext)) return '表格'
  if (['zip', 'rar', '7z', 'tar', 'gz'].includes(ext)) return '压缩包'
  if (['js', 'jsx', 'ts', 'tsx', 'vue', 'html', 'css', 'scss', 'py', 'go', 'rs', 'java'].includes(ext)) return '代码'
  if (['json', 'jsonl', 'yaml', 'yml', 'xml'].includes(ext)) return '数据'
  return `${ext.toUpperCase()} 文件`
}

export function displayMtime(node: KnowledgeFileNode): string {
  return node.mtime || '-'
}

export function displayIngestedAt(node: KnowledgeFileNode): string {
  if (node.isDir || node.indexStatus === 'indexed' || node.indexStatus === 'clean') {
    return node.ingestedAt || '-'
  }
  return '-'
}

export function nodeSize(node: KnowledgeFileNode): number {
  if (!node.isDir) {
    return node.size ?? 0
  }
  return (node.children ?? []).reduce((total, child) => total + nodeSize(child), 0)
}

export function formatSize(size: number): string {
  if (size < 1024) return `${size} B`
  const units = ['KB', 'MB', 'GB', 'TB']
  let value = size / 1024
  let unitIndex = 0
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024
    unitIndex += 1
  }
  return `${value.toFixed(value >= 10 ? 0 : 1)} ${units[unitIndex]}`
}
