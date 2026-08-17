/*
 * Obsidian-style bidirectional-link graph adapter.
 *
 * Usage:
 * Convert knowledge-tree files plus loaded Markdown sources into the existing
 * reusable graph model. Normal wiki links and embeds become separate weighted
 * edges while every node keeps its real path for workspace navigation.
 */

import { findWikiLinkTokens, flattenWikiFiles, resolveWikiTargetPath } from '@/components/editor_workspace/wikiLinks'
import type { KnowledgeFileNode } from '@/types/knowledge'

import type { KnowledgeGraphLink, KnowledgeGraphModel, KnowledgeGraphNode } from './graphTypes'

/** Markdown source text keyed by knowledge-root-relative path. */
export type WikiLinkDocumentSources = Record<string, string>

/** Returns whether a knowledge file participates as a source document. */
function isMarkdownPath(path: string): boolean {
  return /\.(?:md|markdown)$/iu.test(path)
}

/** Removes literal-code and Obsidian-comment regions that are not real links. */
function linkBearingMarkdown(source: string): string {
  return source
    .replace(/^(?:```|~~~)[^\n]*\n[\s\S]*?^(?:```|~~~)\s*$/gmu, '')
    .replace(/`[^`\n]*`/gu, '')
    .replace(/%%[\s\S]*?%%/gu, '')
}

/** Converts one file node to a rootless graph node with a stable circular seed. */
function createDocumentNode(node: KnowledgeFileNode, index: number, total: number): KnowledgeGraphNode {
  const angle = total > 0 ? (index / total) * Math.PI * 2 : 0
  const markdown = isMarkdownPath(node.path)
  return {
    id: node.path,
    label: node.name.replace(/\.(?:md|markdown)$/iu, ''),
    path: node.path,
    kind: markdown ? 'document' : 'file',
    extension: node.name.includes('.') ? node.name.split('.').pop()?.toLocaleLowerCase() : undefined,
    depth: 0,
    siblingIndex: index,
    siblingCount: total,
    ringIndex: 0,
    radius: markdown ? 7 : 5,
    targetX: Math.cos(angle) * 120,
    targetY: Math.sin(angle) * 120,
    x: Math.cos(angle) * 120,
    y: Math.sin(angle) * 120,
  }
}

/** Builds the rootless graph and aggregates repeated links as edge weights. */
export function buildWikiLinkGraph(
  tree: KnowledgeFileNode[],
  documents: WikiLinkDocumentSources,
): KnowledgeGraphModel {
  const files = flattenWikiFiles(tree)
  const fileByPath = new Map(files.map((node) => [node.path, node]))
  const includedPaths = new Set(files.filter((node) => isMarkdownPath(node.path)).map((node) => node.path))
  const weightedLinks = new Map<string, KnowledgeGraphLink>()

  for (const [sourcePath, source] of Object.entries(documents)) {
    if (!fileByPath.has(sourcePath) || !isMarkdownPath(sourcePath)) continue
    for (const token of findWikiLinkTokens(linkBearingMarkdown(source))) {
      const targetPath = resolveWikiTargetPath(token.destination.file, tree, sourcePath)
      if (!targetPath || !fileByPath.has(targetPath)) continue
      includedPaths.add(targetPath)
      const kind = token.embed ? 'embed' : 'reference'
      const key = `${kind}\u0000${sourcePath}\u0000${targetPath}`
      const existing = weightedLinks.get(key)
      if (existing) {
        existing.weight = (existing.weight ?? 1) + 1
      } else {
        weightedLinks.set(key, {
          id: `${kind}:${sourcePath}->${targetPath}`,
          source: sourcePath,
          target: targetPath,
          kind,
          weight: 1,
        })
      }
    }
  }

  const includedFiles = [...includedPaths]
    .map((path) => fileByPath.get(path))
    .filter((node): node is KnowledgeFileNode => Boolean(node))
    .sort((left, right) => left.path.localeCompare(right.path, 'zh-Hans-CN'))
  return {
    nodes: includedFiles.map((node, index) => createDocumentNode(node, index, includedFiles.length)),
    links: [...weightedLinks.values()],
  }
}
