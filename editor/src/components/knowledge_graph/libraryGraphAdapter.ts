/*
 * Virtual-library graph adapter.
 *
 * Usage:
 * Convert user-curated library books and collections into the reusable graph
 * protocol. Collections become virtual-group nodes and books reuse file nodes
 * so the graph behaves like the file-tree view while preserving library tags.
 */

import type { LibraryItem } from '@/types/knowledge'

import type { KnowledgeGraphLink, KnowledgeGraphModel, KnowledgeGraphNode } from './graphTypes'

export interface LibraryGraphAdapterOptions {
  rootLabel: string
  rootId?: string
}

const DEFAULT_ROOT_ID = '__virtual_library_root__'

function normalizeExtension(name: string): string {
  const dotIndex = name.lastIndexOf('.')
  if (dotIndex <= 0 || dotIndex === name.length - 1) {
    return ''
  }
  return name.slice(dotIndex + 1).toLowerCase()
}

function itemNodeId(item: LibraryItem): string {
  return item.item_type === 'collection' ? `library:${item.item_id}` : `library-book:${item.item_id}`
}

function createLink(source: string, target: string): KnowledgeGraphLink {
  return {
    id: `${source}->${target}`,
    source,
    target,
    kind: 'parent-child',
  }
}

function appendItems(
  items: LibraryItem[],
  allItems: LibraryItem[],
  parentId: string,
  depth: number,
  nodes: KnowledgeGraphNode[],
  links: KnowledgeGraphLink[],
) {
  const sorted = [...items].sort((left, right) => {
    if (left.item_type !== right.item_type) {
      return left.item_type === 'collection' ? -1 : 1
    }
    return left.display_title.localeCompare(right.display_title, 'zh-Hans-CN')
  })
  sorted.forEach((item, siblingIndex) => {
    const isCollection = item.item_type === 'collection'
    const graphNode: KnowledgeGraphNode = {
      id: itemNodeId(item),
      label: item.display_title,
      path: isCollection ? '' : item.source_path,
      kind: isCollection ? 'virtual-group' : 'file',
      extension: isCollection ? 'collection' : normalizeExtension(item.source_name || item.source_path),
      depth,
      parentId,
      siblingIndex,
      siblingCount: sorted.length,
      ringIndex: 0,
      radius: isCollection ? Math.max(7, 13 - depth) : Math.max(4, 9 - Math.min(depth, 4)),
      targetX: 0,
      targetY: 0,
    }
    nodes.push(graphNode)
    links.push(createLink(parentId, graphNode.id))
    if (isCollection) {
      appendItems(
        allItems.filter((child) => child.parent_id === item.item_id),
        allItems,
        graphNode.id,
        depth + 1,
        nodes,
        links,
      )
    }
  })
}

export function buildLibraryGraph(
  items: LibraryItem[],
  options: LibraryGraphAdapterOptions,
): KnowledgeGraphModel {
  const rootId = options.rootId ?? DEFAULT_ROOT_ID
  const rootItems = items.filter((item) => !item.parent_id)
  const nodes: KnowledgeGraphNode[] = [
    {
      id: rootId,
      label: options.rootLabel || '图书馆',
      path: '',
      kind: 'library',
      depth: 0,
      siblingIndex: 0,
      siblingCount: 1,
      ringIndex: 0,
      radius: 31,
      targetX: 0,
      targetY: 0,
    },
  ]
  const links: KnowledgeGraphLink[] = []
  appendItems(rootItems, items, rootId, 1, nodes, links)
  return { nodes, links }
}
