/*
 * Semantic knowledge graph adapter.
 *
 * Usage:
 * Convert backend knowledge graph nodes/links into a flat, free-form graph
 * model suitable for the d3-force visualization. Unlike the file-tree adapter,
 * the semantic graph has no root node — entities and documents float freely
 * and are connected only by their semantic relation edges.
 */

import type { KnowledgeSemanticGraphResponse } from '@/types/knowledge'

import type { KnowledgeGraphLink, KnowledgeGraphModel, KnowledgeGraphNode, KnowledgeGraphNodeKind } from './graphTypes'

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

/** Build a flat, rootless graph model from backend semantic graph payload. */
export function buildSemanticKnowledgeGraph(
  payload: KnowledgeSemanticGraphResponse | null,
): KnowledgeGraphModel {
  const backendNodes = payload?.nodes ?? []
  const nodeCount = backendNodes.length

  // Spread nodes in a circle as initial positions so d3-force doesn't
  // pile everything at the canvas center.  The force simulation will
  // pull related nodes together naturally.
  const radius = Math.max(120, nodeCount * 16)
  const nodes: KnowledgeGraphNode[] = backendNodes.map((node, index) => {
    const angle = (index / Math.max(1, nodeCount)) * Math.PI * 2
    return {
      id: node.id,
      label: node.kind === 'entity' && node.entity_type
        ? `${node.entity_type}: ${node.label}`
        : node.label,
      path: node.kind === 'document' ? documentPath(node) : '',
      kind: graphNodeKind(node.kind),
      extension: node.entity_type,
      depth: 0,
      siblingIndex: index,
      siblingCount: nodeCount,
      ringIndex: 0,
      radius: nodeRadius(node.kind),
      targetX: Math.cos(angle) * radius,
      targetY: Math.sin(angle) * radius,
      x: Math.cos(angle) * radius,
      y: Math.sin(angle) * radius,
    }
  })

  const links: KnowledgeGraphLink[] = (payload?.links ?? []).map((link) => ({
    id: link.id,
    source: link.source,
    target: link.target,
    kind: link.kind || 'semantic',
    weight: link.weight,
  }))

  return { nodes, links }
}
