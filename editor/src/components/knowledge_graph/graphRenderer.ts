/*
 * Canvas renderer for reusable knowledge graphs.
 *
 * Usage:
 * Draw a KnowledgeGraphModel onto any 2D canvas context. This file does not
 * depend on Vue or d3-force and can be moved into another application together
 * with graphTypes.ts.
 */

import type {
  KnowledgeGraphLink,
  KnowledgeGraphModel,
  KnowledgeGraphNode,
  KnowledgeGraphRenderState,
  KnowledgeGraphRenderTheme,
} from './graphTypes'

const EXTENSION_COLORS = new Map<string, string>([
  ['txt', '#6f63f6'],
  ['json', '#e2a72e'],
  ['yaml', '#e2a72e'],
  ['yml', '#e2a72e'],
  ['ts', '#3178c6'],
  ['tsx', '#3178c6'],
  ['js', '#c8a000'],
  ['vue', '#26a269'],
  ['py', '#366fb3'],
  ['pdf', '#eb2463'],
  ['docx', '#3b5bdb'],
  ['xlsx', '#26a269'],
])

function currentUiFont(): string {
  if (typeof document === 'undefined') {
    return 'system-ui, sans-serif'
  }
  return getComputedStyle(document.documentElement).getPropertyValue('--font-ui').trim() || 'system-ui, sans-serif'
}

function linkNode(endpoint: string | KnowledgeGraphNode, nodesById: Map<string, KnowledgeGraphNode>) {
  return typeof endpoint === 'string' ? nodesById.get(endpoint) : endpoint
}

function nodeColor(node: KnowledgeGraphNode, theme: KnowledgeGraphRenderTheme): string {
  if (node.kind === 'root') {
    return theme.root
  }
  if (node.kind === 'folder') {
    return theme.folder
  }
  if (node.kind === 'document') {
    return theme.root
  }
  if (node.kind === 'entity') {
    return theme.accent
  }
  const extension = node.extension ?? ''
  if (extension === 'md' || extension === 'markdown') {
    return theme.root
  }
  return EXTENSION_COLORS.get(extension) ?? theme.file
}

function shouldShowLabel(node: KnowledgeGraphNode, state: KnowledgeGraphRenderState): boolean {
  const isActive = node.id === state.hoveredNodeId || node.id === state.selectedNodeId
  if (!state.showLabels) {
    return node.id === state.hoveredNodeId
  }
  if (node.kind === 'root' || node.kind === 'folder' || node.kind === 'document') {
    return true
  }
  return state.viewport.scale > 0.92 || isActive
}

function endpointId(endpoint: string | KnowledgeGraphNode): string {
  return typeof endpoint === 'string' ? endpoint : endpoint.id
}

function collectRelatedNodeIds(model: KnowledgeGraphModel, state: KnowledgeGraphRenderState): Set<string> {
  const baseNodeIds = new Set([state.hoveredNodeId, state.selectedNodeId].filter(Boolean))
  const relatedNodeIds = new Set(baseNodeIds)
  for (const link of model.links) {
    const sourceId = endpointId(link.source)
    const targetId = endpointId(link.target)
    if (baseNodeIds.has(sourceId)) {
      relatedNodeIds.add(targetId)
    }
    if (baseNodeIds.has(targetId)) {
      relatedNodeIds.add(sourceId)
    }
  }
  return relatedNodeIds
}

function drawGrid(ctx: CanvasRenderingContext2D, width: number, height: number, theme: KnowledgeGraphRenderTheme) {
  const step = 32
  ctx.save()
  ctx.strokeStyle = theme.grid
  ctx.lineWidth = 1
  for (let x = 0; x < width; x += step) {
    ctx.beginPath()
    ctx.moveTo(x, 0)
    ctx.lineTo(x, height)
    ctx.stroke()
  }
  for (let y = 0; y < height; y += step) {
    ctx.beginPath()
    ctx.moveTo(0, y)
    ctx.lineTo(width, y)
    ctx.stroke()
  }
  ctx.restore()
}

function drawLink(
  ctx: CanvasRenderingContext2D,
  link: KnowledgeGraphLink,
  nodesById: Map<string, KnowledgeGraphNode>,
  state: KnowledgeGraphRenderState,
  theme: KnowledgeGraphRenderTheme,
  relatedNodeIds: Set<string>,
) {
  const source = linkNode(link.source, nodesById)
  const target = linkNode(link.target, nodesById)
  if (!source || !target) {
    return
  }
  const sourceActive = source.id === state.hoveredNodeId || source.id === state.selectedNodeId
  const targetActive = target.id === state.hoveredNodeId || target.id === state.selectedNodeId
  const hasHover = Boolean(state.hoveredNodeId)
  const isRelated = relatedNodeIds.has(source.id) && relatedNodeIds.has(target.id)
  ctx.save()
  ctx.globalAlpha = hasHover && !isRelated ? 0.2 : 1
  ctx.beginPath()
  ctx.moveTo(source.x ?? source.targetX, source.y ?? source.targetY)
  ctx.lineTo(target.x ?? target.targetX, target.y ?? target.targetY)
  ctx.strokeStyle = sourceActive || targetActive ? theme.edgeActive : theme.edge
  ctx.lineWidth = sourceActive || targetActive ? 2 : 0.85
  ctx.stroke()
  ctx.restore()
}

function drawNode(
  ctx: CanvasRenderingContext2D,
  node: KnowledgeGraphNode,
  state: KnowledgeGraphRenderState,
  theme: KnowledgeGraphRenderTheme,
  relatedNodeIds: Set<string>,
) {
  const x = node.x ?? node.targetX
  const y = node.y ?? node.targetY
  const isSelected = node.id === state.selectedNodeId
  const isHovered = node.id === state.hoveredNodeId
  const hasHover = Boolean(state.hoveredNodeId)
  const isRelated = relatedNodeIds.has(node.id)
  const color = nodeColor(node, theme)
  ctx.save()
  ctx.globalAlpha = hasHover && !isRelated ? 0.38 : 1
  if (isHovered) {
    ctx.beginPath()
    ctx.arc(x, y, node.radius + 12, 0, Math.PI * 2)
    ctx.fillStyle = theme.edgeActive
    ctx.globalAlpha = 0.18
    ctx.fill()
    ctx.globalAlpha = 1
    ctx.shadowColor = theme.edgeActive
    ctx.shadowBlur = 16
  }
  ctx.beginPath()
  ctx.arc(x, y, node.radius, 0, Math.PI * 2)
  if (node.kind === 'folder' || node.kind === 'entity') {
    ctx.setLineDash([4, 3])
    ctx.fillStyle = theme.surface
    ctx.strokeStyle = color
    ctx.lineWidth = isHovered ? 3 : isSelected ? 2.4 : 1.4
    ctx.fill()
    ctx.stroke()
  } else {
    ctx.fillStyle = color
    ctx.strokeStyle = isSelected || isHovered ? theme.selected : theme.surface
    ctx.lineWidth = isHovered ? 4 : isSelected ? 3 : 1.5
    ctx.fill()
    ctx.stroke()
  }
  if (isSelected || isHovered) {
    ctx.beginPath()
    ctx.setLineDash([])
    ctx.arc(x, y, node.radius + 7, 0, Math.PI * 2)
    ctx.strokeStyle = isSelected ? theme.selected : theme.edgeActive
    ctx.lineWidth = 1.2
    ctx.stroke()
  }
  ctx.restore()
}

function drawLabel(
  ctx: CanvasRenderingContext2D,
  node: KnowledgeGraphNode,
  state: KnowledgeGraphRenderState,
  theme: KnowledgeGraphRenderTheme,
  relatedNodeIds: Set<string>,
) {
  if (!shouldShowLabel(node, state)) {
    return
  }
  const x = node.x ?? node.targetX
  const y = node.y ?? node.targetY
  const hasHover = Boolean(state.hoveredNodeId)
  const isRelated = relatedNodeIds.has(node.id)
  const label = node.label.length > 34 ? `${node.label.slice(0, 31)}...` : node.label
  ctx.save()
  ctx.globalAlpha = hasHover && !isRelated ? 0.4 : 1
  const baseFontSize = node.kind === 'root' || node.id === state.hoveredNodeId ? 13 : 11
  ctx.font = `${Math.round(baseFontSize / Math.max(state.viewport.scale, 0.1))}px ${currentUiFont()}`
  ctx.textAlign = 'center'
  ctx.textBaseline = 'top'
  ctx.fillStyle = node.id === state.hoveredNodeId || node.id === state.selectedNodeId ? theme.text : theme.mutedText
  ctx.fillText(label, x, y + node.radius + 7)
  ctx.restore()
}

/** Draw the full graph to the provided Canvas 2D context. */
export function drawKnowledgeGraph(
  ctx: CanvasRenderingContext2D,
  model: KnowledgeGraphModel,
  state: KnowledgeGraphRenderState,
  theme: KnowledgeGraphRenderTheme,
  width: number,
  height: number,
) {
  const nodesById = new Map(model.nodes.map((node) => [node.id, node]))
  const relatedNodeIds = collectRelatedNodeIds(model, state)
  ctx.save()
  ctx.clearRect(0, 0, width, height)
  ctx.fillStyle = theme.canvas
  ctx.fillRect(0, 0, width, height)
  drawGrid(ctx, width, height, theme)
  ctx.translate(state.viewport.x, state.viewport.y)
  ctx.scale(state.viewport.scale, state.viewport.scale)
  model.links.forEach((link) => drawLink(ctx, link, nodesById, state, theme, relatedNodeIds))
  model.nodes.forEach((node) => drawNode(ctx, node, state, theme, relatedNodeIds))
  model.nodes.forEach((node) => drawLabel(ctx, node, state, theme, relatedNodeIds))
  ctx.restore()
}
