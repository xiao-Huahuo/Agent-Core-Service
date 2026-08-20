/*
 * Incoming wiki-link query for the active Markdown document.
 *
 * Usage:
 * Build backlinks from the already supported wiki-link syntax while keeping
 * each source token verbatim for the editor bottom panel.
 */

import type { KnowledgeFileNode } from '@/types/knowledge'
import { findWikiLinkTokens, resolveWikiTargetPath } from './wikiLinks'

export interface BacklinkOccurrence {
  raw: string
  targetKind: 'article' | 'heading' | 'block'
  targetLabel: string
}

export interface BacklinkEntry {
  path: string
  name: string
  occurrences: BacklinkOccurrence[]
}

function basename(path: string): string {
  return path.replace(/\\/g, '/').split('/').pop() ?? path
}

/** Returns every source document whose wiki syntax resolves to currentPath. */
export function buildBacklinks(
  currentPath: string,
  tree: KnowledgeFileNode[],
  documents: Record<string, string>,
): BacklinkEntry[] {
  const normalizedCurrentPath = currentPath.replace(/\\/g, '/')
  return Object.entries(documents)
    .flatMap(([sourcePath, content]) => {
      const occurrences: BacklinkOccurrence[] = []
      for (const token of findWikiLinkTokens(content)) {
        const resolvedPath = resolveWikiTargetPath(token.destination.file, tree, sourcePath)
        if (resolvedPath !== normalizedCurrentPath) continue
        if (token.destination.heading) {
          occurrences.push({
            raw: token.raw,
            targetKind: 'heading',
            targetLabel: token.destination.heading,
          })
        } else if (token.destination.blockId) {
          occurrences.push({
            raw: token.raw,
            targetKind: 'block',
            targetLabel: token.destination.blockId,
          })
        } else {
          occurrences.push({ raw: token.raw, targetKind: 'article', targetLabel: '' })
        }
      }
      return occurrences.length > 0
        ? [{ path: sourcePath, name: basename(sourcePath), occurrences }]
        : []
    })
    .sort((left, right) => left.name.localeCompare(right.name, 'zh-CN') || left.path.localeCompare(right.path, 'zh-CN'))
}
