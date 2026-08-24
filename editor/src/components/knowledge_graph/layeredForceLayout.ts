/*
 * Shared semantic-style force layout.
 *
 * Usage:
 * Create the same unpinned, continuously responsive d3-force simulation for
 * every graph model that follows graphTypes.ts.
 */

import {
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
} from 'd3-force'
import type { Simulation } from 'd3-force'

import type { KnowledgeGraphLink, KnowledgeGraphModel, KnowledgeGraphNode, LayeredForceLayoutOptions } from './graphTypes'

/** Shared force options used by all four graph views. */
export const SEMANTIC_FORCE_OPTIONS: LayeredForceLayoutOptions = {
  maxNodesPerRing: 14,
  baseRingRadius: 96,
  ringGap: 68,
  collisionPadding: 7,
  anchorStrength: 0.0025,
  chargeStrength: -48,
}

/**
 * Custom force that repels document nodes from each other, while not affecting
 * entity nodes. This avoids the cross-type repulsion problem of forceManyBody
 * where a high-charge document would also strongly push entities away.
 */
function forceDocumentRepulsion(strength: number) {
  let nodes: KnowledgeGraphNode[]

  function force(alpha: number) {
    for (let i = 0; i < nodes.length; i++) {
      const a = nodes[i]!
      if (a.kind !== 'document') continue
      for (let j = i + 1; j < nodes.length; j++) {
        const b = nodes[j]!
        if (b.kind !== 'document') continue
        const dx = (a.x ?? a.targetX) - (b.x ?? b.targetX)
        const dy = (a.y ?? a.targetY) - (b.y ?? b.targetY)
        const distSq = dx * dx + dy * dy
        if (distSq < 1) continue
        const dist = Math.sqrt(distSq)
        const forceMag = alpha * strength / Math.max(dist * dist, 100)
        const fx = (dx / dist) * forceMag
        const fy = (dy / dist) * forceMag
        a.vx = (a.vx ?? 0) + fx
        a.vy = (a.vy ?? 0) + fy
        b.vx = (b.vx ?? 0) - fx
        b.vy = (b.vy ?? 0) - fy
      }
    }
  }

  force.initialize = (_nodes: KnowledgeGraphNode[]) => {
    nodes = _nodes
  }

  return force
}

/** Create a d3-force simulation over the reusable graph model. */
export function createLayeredForceSimulation(
  model: KnowledgeGraphModel,
  _width: number,
  _height: number,
  partialOptions?: Partial<LayeredForceLayoutOptions>,
): Simulation<KnowledgeGraphNode, KnowledgeGraphLink> {
  const options = { ...SEMANTIC_FORCE_OPTIONS, ...partialOptions }
  const simulation = forceSimulation<KnowledgeGraphNode>(model.nodes)
    .force(
      'link',
      forceLink<KnowledgeGraphNode, KnowledgeGraphLink>(model.links)
        .id((node) => node.id)
        .distance((link) => {
          const source = typeof link.source === 'object' ? link.source : null
          const target = typeof link.target === 'object' ? link.target : null
          return source?.kind === 'entity' && target?.kind === 'entity' ? 76 : 54
        })
        .strength((link) => {
          const source = typeof link.source === 'object' ? link.source : null
          const target = typeof link.target === 'object' ? link.target : null
          const bothEntity = source?.kind === 'entity' && target?.kind === 'entity'
          if (bothEntity) return Math.min(0.3, (link.weight ?? 0.5) * 0.2 + 0.1)
          return Math.min(0.45, (link.weight ?? 0.5) * 0.2 + 0.25)
        }),
    )
    .force(
      'charge',
      forceManyBody<KnowledgeGraphNode>().strength((node) => {
        if (node.kind === 'entity') return options.chargeStrength
        if (node.kind === 'document') return options.chargeStrength * 0.45
        return options.chargeStrength * 0.65
      }),
    )
    .force('collide', forceCollide<KnowledgeGraphNode>().radius((node) => node.radius + options.collisionPadding))
    .force('document-repulsion', forceDocumentRepulsion(5000))
    .alpha(0.12)
    .alphaDecay(0)
    .alphaMin(0)
    .velocityDecay(0.48)
  return simulation
}
