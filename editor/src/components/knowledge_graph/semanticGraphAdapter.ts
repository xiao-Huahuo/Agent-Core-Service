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

function nodeRadius(kind: string, connectionCount: number): number {
  if (kind === 'document') {
    return 24
  }
  if (kind === 'entity') {
    const baseSize = 5
    const increase = Math.min(connectionCount * baseSize * 0.1, baseSize * 5.0)
    return Math.round(baseSize + increase)
  }
  return 5
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

  // Count connections per node from backend links
  const connectionCounts = new Map<string, number>()
  for (const link of payload?.links ?? []) {
    connectionCounts.set(link.source, (connectionCounts.get(link.source) ?? 0) + 1)
    connectionCounts.set(link.target, (connectionCounts.get(link.target) ?? 0) + 1)
  }

  // Spread nodes in a circle as initial positions so d3-force doesn't
  // pile everything at the canvas center.  The force simulation will
  // pull related nodes together naturally.
  // Start nodes in a compact cluster.  The gentle semantic repulsion will
  // spread them apart naturally; starting too wide makes the link force
  // struggle to pull connected nodes together.
  const radius = Math.min(500, Math.max(180, nodeCount * 5))
  const nodes: KnowledgeGraphNode[] = backendNodes.map((node, index) => {
    const angle = (index / Math.max(1, nodeCount)) * Math.PI * 2
    return {
      id: node.id,
      label: node.label,
      path: node.kind === 'document' ? documentPath(node) : '',
      kind: graphNodeKind(node.kind),
      extension: node.entity_type,
      depth: 0,
      siblingIndex: index,
      siblingCount: nodeCount,
      ringIndex: 0,
      radius: nodeRadius(node.kind, connectionCounts.get(node.id) ?? 0),
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
