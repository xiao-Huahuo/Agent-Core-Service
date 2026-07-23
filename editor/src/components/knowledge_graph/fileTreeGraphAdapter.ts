/*
 * File-tree to graph adapter.
 *
 * Usage:
 * Convert MetaWeave's knowledge file tree into the reusable graph protocol.
 * This module contains no rendering or Vue logic so another application can
 * reuse the same adapter or replace it with its own data source.
 */

import type { KnowledgeFileNode } from '@/types/knowledge'

import type { KnowledgeGraphLink, KnowledgeGraphModel, KnowledgeGraphNode } from './graphTypes'

/** Options for building a file-tree graph model. */
export interface FileTreeGraphAdapterOptions {
  /** Label for the synthetic root node. */
  rootLabel: string
  /** Stable id for the synthetic root node. */
  rootId?: string
}

const DEFAULT_ROOT_ID = '__knowledge_root__'

function normalizeExtension(name: string): string {
  const dotIndex = name.lastIndexOf('.')
  if (dotIndex <= 0 || dotIndex === name.length - 1) {
    return ''
  }
  return name.slice(dotIndex + 1).toLowerCase()
}

function nodeRadius(node: KnowledgeFileNode, depth: number): number {
  if (node.isDir) {
    return Math.max(6, Math.round((15 - depth) * 2 / 3))
  }
  return Math.max(3, Math.round((10 - Math.min(depth, 4)) * 2 / 3))
}

function sortedChildren(nodes: KnowledgeFileNode[]): KnowledgeFileNode[] {
  return [...nodes].sort((left, right) => {
    if (left.isDir !== right.isDir) {
      return left.isDir ? -1 : 1
    }
    return left.name.localeCompare(right.name, 'zh-Hans-CN')
  })
}

function createLink(source: string, target: string): KnowledgeGraphLink {
  return {
    id: `${source}->${target}`,
    source,
    target,
    kind: 'parent-child',
  }
}

function appendTreeNodes(
  sourceNodes: KnowledgeFileNode[],
  parentId: string,
  depth: number,
  targetNodes: KnowledgeGraphNode[],
  targetLinks: KnowledgeGraphLink[],
) {
  const children = sortedChildren(sourceNodes)
  children.forEach((node, siblingIndex) => {
    const graphNode: KnowledgeGraphNode = {
      id: node.path,
      label: node.name,
      path: node.path,
      kind: node.isDir ? 'folder' : 'file',
      extension: node.isDir ? undefined : normalizeExtension(node.name),
      depth,
      parentId,
      siblingIndex,
      siblingCount: children.length,
      ringIndex: 0,
      radius: nodeRadius(node, depth),
      targetX: 0,
      targetY: 0,
    }
    targetNodes.push(graphNode)
    targetLinks.push(createLink(parentId, graphNode.id))
    if (node.children && node.children.length > 0) {
      appendTreeNodes(node.children, graphNode.id, depth + 1, targetNodes, targetLinks)
    }
  })
}

/** Build the first reusable graph model from a knowledge file tree. */
export function buildFileTreeGraph(
  tree: KnowledgeFileNode[],
  options: FileTreeGraphAdapterOptions,
): KnowledgeGraphModel {
  const rootId = options.rootId ?? DEFAULT_ROOT_ID
  const nodes: KnowledgeGraphNode[] = [
    {
      id: rootId,
      label: options.rootLabel || 'Knowledge Root',
      path: '',
      kind: 'root',
      depth: 0,
      siblingIndex: 0,
      siblingCount: 1,
      ringIndex: 0,
      radius: 13,
      targetX: 0,
      targetY: 0,
    },
  ]
  const links: KnowledgeGraphLink[] = []
  appendTreeNodes(tree, rootId, 1, nodes, links)
  return { nodes, links }
}
