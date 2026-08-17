/*
 * Obsidian-style wiki-link syntax and knowledge-tree helpers.
 *
 * Usage:
 * CodeEditor uses trigger and suggestion helpers while MarkdownPreview uses
 * the same parser, resolver, and section extractor for navigation and embeds.
 */

import type { KnowledgeFileNode } from '@/types/knowledge'

/** Maximum nested ![[...]] expansion depth, matching the editor contract. */
export const WIKI_EMBED_MAX_DEPTH = 5

/** Parsed destination shared by normal wiki links and embedded wiki links. */
export interface WikiLinkDestination {
  file: string
  heading: string
  blockId: string
  alias: string
}

/** Active incomplete wiki token immediately before the textarea caret. */
export interface WikiLinkTrigger {
  start: number
  embed: boolean
  query: string
}

/** One file candidate displayed by the wiki-link suggestion menu. */
export interface WikiLinkSuggestion {
  path: string
  title: string
  folder: string
  target: string
}

/** One complete wiki token found inside rendered Markdown text. */
export interface WikiLinkToken {
  raw: string
  embed: boolean
  destination: WikiLinkDestination
  start: number
  end: number
}

/** Converts Windows separators and dot segments to one knowledge-relative path. */
function normalizePath(value: string): string {
  const parts: string[] = []
  for (const part of value.trim().replace(/\\/g, '/').replace(/^\/+/, '').split('/')) {
    if (!part || part === '.') continue
    if (part === '..') {
      parts.pop()
      continue
    }
    parts.push(part)
  }
  return parts.join('/')
}

/** Removes only a Markdown extension because Obsidian wiki targets omit it. */
function withoutMarkdownExtension(value: string): string {
  return value.replace(/\.(?:md|markdown)$/iu, '')
}

/** Returns the parent directory with a trailing slash for menu presentation. */
function parentFolder(path: string): string {
  const normalized = normalizePath(path)
  const slash = normalized.lastIndexOf('/')
  return slash >= 0 ? `${normalized.slice(0, slash)}/` : '/'
}

/** Flattens the existing eager knowledge tree without inventing another store. */
export function flattenWikiFiles(nodes: KnowledgeFileNode[]): KnowledgeFileNode[] {
  return nodes.flatMap((node) => (
    node.isDir ? flattenWikiFiles(node.children ?? []) : [node]
  ))
}

/** Parses file, #heading, ^block, and |alias portions of a wiki destination. */
export function parseWikiLink(rawDestination: string): WikiLinkDestination {
  const [targetPart = '', ...aliasParts] = rawDestination.split('|')
  const alias = aliasParts.join('|').trim()
  const blockMatch = targetPart.match(/(?:#)?\^([^#^]+)$/u)
  const blockId = blockMatch?.[1]?.trim() ?? ''
  const targetWithoutBlock = blockMatch
    ? targetPart.slice(0, blockMatch.index)
    : targetPart
  const headingIndex = targetWithoutBlock.indexOf('#')
  return {
    file: (headingIndex >= 0 ? targetWithoutBlock.slice(0, headingIndex) : targetWithoutBlock).trim(),
    heading: (headingIndex >= 0 ? targetWithoutBlock.slice(headingIndex + 1) : '').trim(),
    blockId,
    alias,
  }
}

/** Finds all complete [[...]] and ![[...]] tokens outside later DOM filtering. */
export function findWikiLinkTokens(text: string): WikiLinkToken[] {
  const result: WikiLinkToken[] = []
  const pattern = /(!)?\[\[([^\]\n]+)\]\]/gu
  for (const match of text.matchAll(pattern)) {
    const raw = match[0]
    const start = match.index ?? 0
    result.push({
      raw,
      embed: Boolean(match[1]),
      destination: parseWikiLink(match[2] ?? ''),
      start,
      end: start + raw.length,
    })
  }
  return result
}

/** Detects an unclosed [[ or ![[ token at the caret and extracts its file query. */
export function findWikiLinkTrigger(content: string, cursor: number): WikiLinkTrigger | null {
  const beforeCaret = content.slice(0, cursor)
  const match = beforeCaret.match(/(!)?\[\[([^\]\n]*)$/u)
  if (!match || match.index === undefined) return null
  const inner = match[2] ?? ''
  if (/[|#^]/u.test(inner)) return null
  return {
    start: match.index,
    embed: Boolean(match[1]),
    query: inner.trim(),
  }
}

/** Builds sorted, filename-filtered file candidates with their source folders. */
export function wikiLinkSuggestions(
  nodes: KnowledgeFileNode[],
  query: string,
  limit = 80,
): WikiLinkSuggestion[] {
  const normalizedQuery = query.trim().toLocaleLowerCase()
  return flattenWikiFiles(nodes)
    .map((node) => {
      const path = normalizePath(node.path)
      const target = withoutMarkdownExtension(path)
      const title = withoutMarkdownExtension(node.name)
      return { path, title, folder: parentFolder(path), target }
    })
    .filter((item) => (
      !normalizedQuery || item.title.toLocaleLowerCase().includes(normalizedQuery)
        || item.path.toLocaleLowerCase().includes(normalizedQuery)
    ))
    .sort((left, right) => {
      const leftStarts = left.title.toLocaleLowerCase().startsWith(normalizedQuery) ? 0 : 1
      const rightStarts = right.title.toLocaleLowerCase().startsWith(normalizedQuery) ? 0 : 1
      return leftStarts - rightStarts || left.title.localeCompare(right.title, 'zh-CN')
        || left.path.localeCompare(right.path, 'zh-CN')
    })
    .slice(0, limit)
}

/** Resolves a wiki file target using current-folder, full-path, then basename matching. */
export function resolveWikiTargetPath(
  rawFile: string,
  nodes: KnowledgeFileNode[],
  currentPath: string,
): string {
  if (!rawFile.trim()) return normalizePath(currentPath)
  const files = flattenWikiFiles(nodes)
  const target = withoutMarkdownExtension(normalizePath(rawFile)).toLocaleLowerCase()
  const currentFolder = parentFolder(currentPath).replace(/\/$/u, '')
  const relativeTarget = withoutMarkdownExtension(normalizePath(`${currentFolder}/${rawFile}`)).toLocaleLowerCase()
  const comparable = (path: string) => withoutMarkdownExtension(normalizePath(path)).toLocaleLowerCase()
  const exactRelative = files.find((node) => comparable(node.path) === relativeTarget)
  if (exactRelative) return normalizePath(exactRelative.path)
  const exact = files.find((node) => comparable(node.path) === target)
  if (exact) return normalizePath(exact.path)
  const basenameMatches = files.filter((node) => comparable(node.path).split('/').pop() === target.split('/').pop())
  return basenameMatches.length === 1 ? normalizePath(basenameMatches[0]?.path ?? '') : ''
}

/** Normalizes visible heading text for case-insensitive anchor matching. */
export function normalizeWikiAnchor(value: string): string {
  return value
    .replace(/<[^>]+>/gu, '')
    .replace(/[*_~=`]/gu, '')
    .replace(/\s+#+\s*$/u, '')
    .trim()
    .replace(/\s+/gu, ' ')
    .toLocaleLowerCase()
}

/** Extracts a heading subtree or one ^block from Markdown for embedded previews. */
export function extractWikiSection(
  markdown: string,
  anchor: Pick<WikiLinkDestination, 'heading' | 'blockId'>,
): string {
  if (!anchor.heading && !anchor.blockId) return markdown.trim()
  const lines = markdown.split(/\r?\n/u)
  if (anchor.blockId) {
    const escaped = anchor.blockId.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    const blockPattern = new RegExp(`(?:^|\\s)\\^${escaped}(?:\\s|$)`, 'u')
    const line = lines.find((item) => blockPattern.test(item))
    return line?.replace(blockPattern, '').trim() ?? ''
  }
  const target = normalizeWikiAnchor(anchor.heading)
  let start = -1
  let level = 7
  for (let index = 0; index < lines.length; index += 1) {
    const heading = lines[index]?.match(/^(#{1,6})\s+(.+?)\s*$/u)
    if (heading && normalizeWikiAnchor(heading[2] ?? '') === target) {
      start = index
      level = heading[1]?.length ?? 7
      break
    }
  }
  if (start < 0) return ''
  let end = lines.length
  for (let index = start + 1; index < lines.length; index += 1) {
    const heading = lines[index]?.match(/^(#{1,6})\s+/u)
    if (heading && (heading[1]?.length ?? 7) <= level) {
      end = index
      break
    }
  }
  return lines.slice(start, end).join('\n').trim()
}
