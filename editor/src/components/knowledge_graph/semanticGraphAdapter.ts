/*
 * Semantic knowledge graph adapter.
 *
 * Usage:
 * Convert backend knowledge graph nodes/links into the reusable Canvas graph
 * protocol used by KnowledgeGraphCanvas.
 */

import type { KnowledgeSemanticGraphResponse } from '@/types/knowledge'

import type { KnowledgeGraphLink, KnowledgeGraphModel, KnowledgeGraphNode, KnowledgeGraphNodeKind } from './graphTypes'

const ROOT_ID = '__semantic_graph_root__'

function nodeRadius(kind: string): number {
  if (kind === 'document') {
    return 12
  }
  if (kind === 'entity') {
    return 8
  }
  return 7
}

function graphNodeKind(kind: string): KnowledgeGraphNodeKind {
  return kind === 'document' ? 'document' : 'entity'
}

function documentPath(node: { metadata?: Record<string, unknown>; source_uri?: string }): string {
  const relativePath = node.metadata?.relative_path
  if (typeof relativePath === 'string' && relativePath) {
    return relativePath
  }
  return ''
}

/** Build a Canvas graph model from backend semantic graph payload. */
export function buildSemanticKnowledgeGraph(
  payload: KnowledgeSemanticGraphResponse | null,
  rootLabel: string,
): KnowledgeGraphModel {
  const backendNodes = payload?.nodes ?? []
  const rootNode: KnowledgeGraphNode = {
    id: ROOT_ID,
    label: rootLabel || 'Knowledge Graph',
    path: '',
    kind: 'root',
    depth: 0,
    siblingIndex: 0,
    siblingCount: 1,
    ringIndex: 0,
    radius: 20,
    targetX: 0,
    targetY: 0,
  }
  const siblingCount = Math.max(backendNodes.length, 1)
  const nodes: KnowledgeGraphNode[] = [
    rootNode,
    ...backendNodes.map((node, index) => ({
      id: node.id,
      label: node.label,
      path: node.kind === 'document' ? documentPath(node) : '',
      kind: graphNodeKind(node.kind),
      extension: node.entity_type,
      depth: 1,
      parentId: ROOT_ID,
      siblingIndex: index,
      siblingCount,
      ringIndex: 0,
      radius: nodeRadius(node.kind),
      targetX: 0,
      targetY: 0,
    })),
  ]
  const links: KnowledgeGraphLink[] = [
    ...backendNodes
      .filter((node) => node.kind === 'document')
      .map((node) => ({
        id: `${ROOT_ID}->${node.id}`,
        source: ROOT_ID,
        target: node.id,
        kind: 'parent-child',
        weight: 0.2,
      })),
    ...(payload?.links ?? []).map((link) => ({
      id: link.id,
      source: link.source,
      target: link.target,
      kind: link.kind || 'semantic',
      weight: link.weight,
    })),
  ]
  return { nodes, links }
}
