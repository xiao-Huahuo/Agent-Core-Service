/*
 * File-tree filename search helpers.
 *
 * Usage:
 * FileTreePanel filters its recursive tree by filename without changing the
 * tree structure: matching files stay under their ancestors, a matching
 * directory keeps its whole subtree, and non-matching siblings are dropped.
 */

import type { KnowledgeFileNode } from '@/types/knowledge'

export function filterTreeByQuery(nodes: KnowledgeFileNode[], query: string): KnowledgeFileNode[] {
  /** Return a shallow copy keeping only filename matches and their ancestor paths. */

  const needle = query.trim().toLowerCase()
  if (!needle) return nodes
  const result: KnowledgeFileNode[] = []
  for (const node of nodes) {
    const nameMatched = node.name.toLowerCase().includes(needle)
    const filteredChildren = node.children ? filterTreeByQuery(node.children, query) : undefined
    if (nameMatched || (filteredChildren && filteredChildren.length > 0)) {
      result.push({
        ...node,
        children: nameMatched ? node.children : filteredChildren,
      })
    }
  }
  return result
}

export function collectExpandedPathsForFilteredTree(nodes: KnowledgeFileNode[]): Set<string> {
  /** Expand every remaining directory so all search hits stay visible. */

  const paths = new Set<string>()
  function walk(list: KnowledgeFileNode[]) {
    for (const node of list) {
      if (node.isDir) {
        paths.add(node.path)
        if (node.children) walk(node.children)
      }
    }
  }
  walk(nodes)
  return paths
}
