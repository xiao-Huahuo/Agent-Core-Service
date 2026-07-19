/*
 * Material file icon resolver shared by the file tree and file resource manager.
 *
 * Usage:
 * Keep all filename/extension/folder mapping in this module. The mappings come
 * from material-icon-theme's VS Code icon theme JSON instead of local hardcoding.
 */

import materialIcons from 'material-icon-theme/dist/material-icons.json'

import type { KnowledgeFileNode } from '@/types/knowledge'

type IconDefinition = {
  iconPath?: string
}

type MaterialIconManifest = {
  iconDefinitions: Record<string, IconDefinition>
  file: string
  folder: string
  folderExpanded: string
  fileExtensions?: Record<string, string>
  fileNames?: Record<string, string>
  folderNames?: Record<string, string>
  folderNamesExpanded?: Record<string, string>
  light?: {
    fileExtensions?: Record<string, string>
    fileNames?: Record<string, string>
    folderNames?: Record<string, string>
    folderNamesExpanded?: Record<string, string>
  }
}

export type MaterialFileIcon = {
  src: string
  alt: string
}

const manifest = materialIcons as MaterialIconManifest
const iconUrls = import.meta.glob('/node_modules/material-icon-theme/icons/*.svg', {
  eager: true,
  import: 'default',
  query: '?url',
}) as Record<string, string>

const extensionKeys = sortKeysByMatchSpecificity(manifest.fileExtensions)
const lightExtensionKeys = sortKeysByMatchSpecificity(manifest.light?.fileExtensions)
const fileNameKeys = sortKeysByMatchSpecificity(manifest.fileNames)
const lightFileNameKeys = sortKeysByMatchSpecificity(manifest.light?.fileNames)
const resolvedIconCache = new Map<string, MaterialFileIcon>()

function sortKeysByMatchSpecificity(source?: Record<string, string>): string[] {
  return Object.keys(source ?? {}).sort((left, right) => right.length - left.length)
}

function isLightTheme(): boolean {
  return typeof document !== 'undefined' && document.documentElement.getAttribute('data-theme') === 'light'
}

function normalizePath(value: string): string {
  return value.replace(/\\/g, '/').toLowerCase()
}

function basename(path: string): string {
  const normalized = normalizePath(path)
  const parts = normalized.split('/').filter(Boolean)
  return parts[parts.length - 1] ?? normalized
}

function matchNamedIcon(
  fullPath: string,
  name: string,
  source: Record<string, string> | undefined,
  keys: string[],
): string | undefined {
  const normalizedPath = normalizePath(fullPath)
  const normalizedName = basename(name)
  for (const key of keys) {
    const normalizedKey = normalizePath(key)
    if (normalizedName === normalizedKey || normalizedPath === normalizedKey || normalizedPath.endsWith(`/${normalizedKey}`)) {
      return source?.[key]
    }
  }
  return undefined
}

function matchExtensionIcon(
  name: string,
  source: Record<string, string> | undefined,
  keys: string[],
): string | undefined {
  const normalizedName = basename(name)
  for (const key of keys) {
    const normalizedKey = normalizePath(key).replace(/^\./, '')
    if (normalizedName === normalizedKey || normalizedName.endsWith(`.${normalizedKey}`)) {
      return source?.[key]
    }
  }
  return undefined
}

function iconUrl(iconName: string | undefined): string {
  const fallbackIcon = manifest.iconDefinitions[manifest.file]?.iconPath
  const iconPath = iconName ? manifest.iconDefinitions[iconName]?.iconPath : fallbackIcon
  const iconParts = iconPath?.split('/') ?? []
  const fallbackParts = fallbackIcon?.split('/') ?? []
  const svgName = iconParts[iconParts.length - 1] ?? fallbackParts[fallbackParts.length - 1] ?? 'file.svg'
  return iconUrls[`/node_modules/material-icon-theme/icons/${svgName}`] ?? ''
}

function resolveFolderIcon(node: KnowledgeFileNode, expanded = false): string {
  const name = basename(node.name)
  const normalSource = expanded ? manifest.folderNamesExpanded : manifest.folderNames
  const lightSource = expanded ? manifest.light?.folderNamesExpanded : manifest.light?.folderNames
  const defaultFolder = expanded ? manifest.folderExpanded : manifest.folder
  const normalIcon = normalSource?.[name]
  const lightIcon = isLightTheme() ? lightSource?.[name] : undefined
  return lightIcon ?? normalIcon ?? defaultFolder
}

function resolveFileIcon(node: KnowledgeFileNode): string {
  const fullPath = node.path || node.name
  const name = node.name
  const lightIcon = isLightTheme()
    ? matchNamedIcon(fullPath, name, manifest.light?.fileNames, lightFileNameKeys)
      ?? matchExtensionIcon(name, manifest.light?.fileExtensions, lightExtensionKeys)
    : undefined
  return lightIcon
    ?? matchNamedIcon(fullPath, name, manifest.fileNames, fileNameKeys)
    ?? matchExtensionIcon(name, manifest.fileExtensions, extensionKeys)
    ?? manifest.file
}

export function materialFileIconForNode(node: KnowledgeFileNode, expanded = false): MaterialFileIcon {
  const themeKey = isLightTheme() ? 'light' : 'dark'
  const cacheKey = `${themeKey}|${node.isDir ? 'dir' : 'file'}|${expanded ? 'open' : 'closed'}|${normalizePath(node.path || node.name)}|${normalizePath(node.name)}`
  const cached = resolvedIconCache.get(cacheKey)
  if (cached) {
    return cached
  }
  const iconName = node.isDir ? resolveFolderIcon(node, expanded) : resolveFileIcon(node)
  const icon = {
    src: iconUrl(iconName),
    alt: '',
  }
  resolvedIconCache.set(cacheKey, icon)
  return icon
}
