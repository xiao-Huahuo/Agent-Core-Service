/*
 * Knowledge graph geometry helpers.
 *
 * Usage:
 * Convert between screen and world coordinates, hit-test nodes, and compute
 * fit-to-view transforms without depending on Vue or Canvas drawing state.
 */

import type { KnowledgeGraphModel, KnowledgeGraphNode, KnowledgeGraphViewport } from './graphTypes'

/** 2D point used by pointer and graph math. */
export interface GraphPoint {
  x: number
  y: number
}

/** Convert a screen-space point into graph world coordinates. */
export function screenToWorld(point: GraphPoint, viewport: KnowledgeGraphViewport): GraphPoint {
  return {
    x: (point.x - viewport.x) / viewport.scale,
    y: (point.y - viewport.y) / viewport.scale,
  }
}

/** Convert a graph world coordinate into screen space. */
export function worldToScreen(point: GraphPoint, viewport: KnowledgeGraphViewport): GraphPoint {
  return {
    x: point.x * viewport.scale + viewport.x,
    y: point.y * viewport.scale + viewport.y,
  }
}

/** Find the topmost node under a world-space point. */
export function hitTestNode(
  model: KnowledgeGraphModel,
  point: GraphPoint,
  padding = 4,
): KnowledgeGraphNode | null {
  for (let index = model.nodes.length - 1; index >= 0; index -= 1) {
    const node = model.nodes[index]
    if (!node) {
      continue
    }
    const dx = point.x - (node.x ?? node.targetX)
    const dy = point.y - (node.y ?? node.targetY)
    if (Math.hypot(dx, dy) <= node.radius + padding) {
      return node
    }
  }
  return null
}

/** Compute a viewport that fits all nodes inside the available canvas area. */
export function fitGraphToViewport(
  model: KnowledgeGraphModel,
  width: number,
  height: number,
  padding = 80,
): KnowledgeGraphViewport {
  if (model.nodes.length === 0) {
    return { x: width / 2, y: height / 2, scale: 1 }
  }
  const xs = model.nodes.map((node) => node.x ?? node.targetX)
  const ys = model.nodes.map((node) => node.y ?? node.targetY)
  const minX = Math.min(...xs)
  const maxX = Math.max(...xs)
  const minY = Math.min(...ys)
  const maxY = Math.max(...ys)
  const graphWidth = Math.max(1, maxX - minX)
  const graphHeight = Math.max(1, maxY - minY)
  const scale = Math.min(
    1.25,
    Math.max(0.22, Math.min((width - padding * 2) / graphWidth, (height - padding * 2) / graphHeight)),
  )
  const centerX = (minX + maxX) / 2
  const centerY = (minY + maxY) / 2
  return {
    x: width / 2 - centerX * scale,
    y: height / 2 - centerY * scale,
    scale,
  }
}

/** Create a viewport centered on one node. */
export function focusNodeViewport(
  node: KnowledgeGraphNode,
  width: number,
  height: number,
  scale: number,
): KnowledgeGraphViewport {
  const nodeX = node.x ?? node.targetX
  const nodeY = node.y ?? node.targetY
  return {
    x: width / 2 - nodeX * scale,
    y: height / 2 - nodeY * scale,
    scale,
  }
}
