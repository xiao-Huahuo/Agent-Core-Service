/*
 * Layered force layout.
 *
 * Usage:
 * Prepare ring-based target coordinates and create a d3-force simulation for
 * any graph that follows graphTypes.ts. The module is framework-agnostic and
 * can be reused outside Vue.
 */

import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  forceX,
  forceY,
} from 'd3-force'
import type { Simulation } from 'd3-force'

import type { KnowledgeGraphLink, KnowledgeGraphModel, KnowledgeGraphNode, LayeredForceLayoutOptions } from './graphTypes'

/** Default layout values tuned for the editor's file-tree graph. */
export const DEFAULT_LAYERED_FORCE_OPTIONS: LayeredForceLayoutOptions = {
  maxNodesPerRing: 14,
  baseRingRadius: 96,
  ringGap: 68,
  collisionPadding: 7,
  anchorStrength: 0.085,
  chargeStrength: -72,
}

function mergedOptions(options?: Partial<LayeredForceLayoutOptions>): LayeredForceLayoutOptions {
  return { ...DEFAULT_LAYERED_FORCE_OPTIONS, ...options }
}

function linkEndpointId(endpoint: string | KnowledgeGraphNode): string {
  return typeof endpoint === 'string' ? endpoint : endpoint.id
}

function groupedChildren(nodes: KnowledgeGraphNode[]): Map<string, KnowledgeGraphNode[]> {
  const childrenByParent = new Map<string, KnowledgeGraphNode[]>()
  nodes.forEach((node) => {
    if (!node.parentId) {
      return
    }
    const siblings = childrenByParent.get(node.parentId) ?? []
    siblings.push(node)
    childrenByParent.set(node.parentId, siblings)
  })
  childrenByParent.forEach((siblings) => {
    siblings.sort((left, right) => left.siblingIndex - right.siblingIndex)
  })
  return childrenByParent
}

function assignChildTargets(
  parent: KnowledgeGraphNode,
  childrenByParent: Map<string, KnowledgeGraphNode[]>,
  options: LayeredForceLayoutOptions,
) {
  const children = childrenByParent.get(parent.id) ?? []
  children.forEach((child, index) => {
    const maxPerRing = Math.max(6, options.maxNodesPerRing + child.depth * 2)
    const ringIndex = Math.floor(index / maxPerRing)
    const firstIndexInRing = ringIndex * maxPerRing
    const indexInRing = index - firstIndexInRing
    const itemsInRing = Math.min(maxPerRing, children.length - firstIndexInRing)
    const depthBias = Math.max(0, child.depth - 1) * 18
    const radius = options.baseRingRadius + depthBias + ringIndex * options.ringGap
    const angleOffset = child.depth % 2 === 0 ? Math.PI / itemsInRing : 0
    const angle = (indexInRing / Math.max(1, itemsInRing)) * Math.PI * 2 + angleOffset
    child.ringIndex = ringIndex
    child.targetX = parent.targetX + Math.cos(angle) * radius
    child.targetY = parent.targetY + Math.sin(angle) * radius
    if (child.x === undefined || child.y === undefined) {
      child.x = child.targetX
      child.y = child.targetY
    }
    assignChildTargets(child, childrenByParent, options)
  })
}

/** Recompute layered target coordinates in-place for all graph nodes. */
export function prepareLayeredTargets(
  model: KnowledgeGraphModel,
  width: number,
  height: number,
  partialOptions?: Partial<LayeredForceLayoutOptions>,
) {
  const options = mergedOptions(partialOptions)
  const root = model.nodes.find((node) => node.depth === 0) ?? model.nodes[0]
  if (!root) {
    return
  }
  root.targetX = width / 2
  root.targetY = height / 2
  root.x ??= root.targetX
  root.y ??= root.targetY
  const childrenByParent = groupedChildren(model.nodes)
  assignChildTargets(root, childrenByParent, options)
}

/** Create a d3-force simulation over the reusable graph model. */
export function createLayeredForceSimulation(
  model: KnowledgeGraphModel,
  width: number,
  height: number,
  partialOptions?: Partial<LayeredForceLayoutOptions>,
): Simulation<KnowledgeGraphNode, KnowledgeGraphLink> {
  const options = mergedOptions(partialOptions)
  prepareLayeredTargets(model, width, height, options)
  return forceSimulation<KnowledgeGraphNode>(model.nodes)
    .force(
      'link',
      forceLink<KnowledgeGraphNode, KnowledgeGraphLink>(model.links)
        .id((node) => node.id)
        .distance((link) => {
          const sourceId = linkEndpointId(link.source)
          const targetId = linkEndpointId(link.target)
          return sourceId === '' || targetId === '' ? 120 : 86
        })
        .strength((link) => (link.kind === 'parent-child' ? 0.58 : 0.18)),
    )
    .force(
      'charge',
      forceManyBody<KnowledgeGraphNode>().strength((node) => {
        if (node.kind === 'root') {
          return options.chargeStrength * 2.3
        }
        if (node.kind === 'folder') {
          return options.chargeStrength * 1.4
        }
        return options.chargeStrength
      }),
    )
    .force('collide', forceCollide<KnowledgeGraphNode>().radius((node) => node.radius + options.collisionPadding))
    .force('x', forceX<KnowledgeGraphNode>((node) => node.targetX).strength(options.anchorStrength))
    .force('y', forceY<KnowledgeGraphNode>((node) => node.targetY).strength(options.anchorStrength))
    .force('center', forceCenter(width / 2, height / 2))
    .alpha(0.95)
    .alphaDecay(0.035)
}
