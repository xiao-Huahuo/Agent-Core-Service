<!--
  Reusable Canvas knowledge graph component.

  Usage:
  Receives a framework-neutral KnowledgeGraphModel, runs the layered D3 force
  layout, and emits node interaction events. The data adapter and renderer live
  in separate modules so other applications can reuse them without this Vue UI.
-->
<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import type { Simulation } from 'd3-force'

import { fitGraphToViewport, focusNodeViewport, hitTestNode, screenToWorld } from './graphGeometry'
import { drawKnowledgeGraph } from './graphRenderer'
import { createLayeredForceSimulation } from './layeredForceLayout'
import type {
  KnowledgeGraphLink,
  KnowledgeGraphModel,
  KnowledgeGraphNode,
  KnowledgeGraphNodeEvent,
  KnowledgeGraphRenderTheme,
  KnowledgeGraphViewport,
} from './graphTypes'

const props = defineProps<{
  model: KnowledgeGraphModel
  selectedNodeId?: string
}>()

const emit = defineEmits<{
  'node-select': [event: KnowledgeGraphNodeEvent]
  'node-open': [event: KnowledgeGraphNodeEvent]
}>()

const canvasRef = ref<HTMLCanvasElement | null>(null)
const hostRef = ref<HTMLElement | null>(null)
const runtimeModel = shallowRef<KnowledgeGraphModel>({ nodes: [], links: [] })
const hoveredNodeId = ref('')
const selectedNodeId = ref(props.selectedNodeId ?? '')
const viewport = ref<KnowledgeGraphViewport>({ x: 0, y: 0, scale: 1 })
const canvasSize = ref({ width: 1, height: 1 })

let simulation: Simulation<KnowledgeGraphNode, KnowledgeGraphLink> | null = null
let resizeObserver: ResizeObserver | null = null
let animationFrame = 0
let pointerMode: 'none' | 'pan' | 'node' = 'none'
let activePointerId = 0
let draggedNode: KnowledgeGraphNode | null = null
let pointerStart = { x: 0, y: 0 }
let viewportStart: KnowledgeGraphViewport = { x: 0, y: 0, scale: 1 }
let movedDuringPointer = false

const graphStats = computed(() => ({
  nodes: runtimeModel.value.nodes.length,
  links: runtimeModel.value.links.length,
}))

function endpointId(endpoint: string | KnowledgeGraphNode): string {
  return typeof endpoint === 'string' ? endpoint : endpoint.id
}

function cloneGraphModel(model: KnowledgeGraphModel): KnowledgeGraphModel {
  return {
    nodes: model.nodes.map((node) => ({ ...node, fx: null, fy: null })),
    links: model.links.map((link) => ({
      ...link,
      source: endpointId(link.source),
      target: endpointId(link.target),
    })),
  }
}

function toNodeEvent(node: KnowledgeGraphNode): KnowledgeGraphNodeEvent {
  return {
    id: node.id,
    label: node.label,
    path: node.path,
    kind: node.kind,
  }
}

function cssVar(name: string, fallback: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback
}

function readTheme(): KnowledgeGraphRenderTheme {
  const isDark = document.documentElement.getAttribute('data-theme') !== 'light'
  return {
    canvas: cssVar('--color-canvas-soft', isDark ? '#151517' : '#ffffff'),
    grid: isDark ? 'rgba(66, 36, 235, 0.08)' : 'rgba(66, 36, 235, 0.07)',
    text: cssVar('--color-text', isDark ? '#f4f4f6' : '#171721'),
    mutedText: cssVar('--color-text-muted', isDark ? '#8f93a3' : '#707486'),
    edge: isDark ? 'rgba(143, 147, 163, 0.32)' : 'rgba(112, 116, 134, 0.34)',
    edgeActive: cssVar('--color-primary', '#4224eb'),
    root: cssVar('--color-primary', '#4224eb'),
    folder: cssVar('--color-primary', '#4224eb'),
    file: cssVar('--color-text-secondary', isDark ? '#c7c7d1' : '#3f4252'),
    selected: cssVar('--color-accent', '#eb2463'),
    accent: cssVar('--color-accent', '#eb2463'),
    surface: cssVar('--color-surface-raised', isDark ? '#202026' : '#ffffff'),
  }
}

function requestDraw() {
  if (animationFrame) {
    return
  }
  animationFrame = window.requestAnimationFrame(() => {
    animationFrame = 0
    draw()
  })
}

function draw() {
  const canvas = canvasRef.value
  const context = canvas?.getContext('2d')
  if (!canvas || !context) {
    return
  }
  const pixelRatio = window.devicePixelRatio || 1
  context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0)
  drawKnowledgeGraph(
    context,
    runtimeModel.value,
    {
      viewport: viewport.value,
      hoveredNodeId: hoveredNodeId.value,
      selectedNodeId: selectedNodeId.value,
    },
    readTheme(),
    canvasSize.value.width,
    canvasSize.value.height,
  )
}

function resizeCanvas() {
  const canvas = canvasRef.value
  const host = hostRef.value
  if (!canvas || !host) {
    return
  }
  const rect = host.getBoundingClientRect()
  const width = Math.max(1, rect.width)
  const height = Math.max(1, rect.height)
  const pixelRatio = window.devicePixelRatio || 1
  canvasSize.value = { width, height }
  canvas.width = Math.floor(width * pixelRatio)
  canvas.height = Math.floor(height * pixelRatio)
  canvas.style.width = `${width}px`
  canvas.style.height = `${height}px`
  requestDraw()
}

function stopSimulation() {
  simulation?.stop()
  simulation = null
}

function startSimulation(shouldFit = true) {
  stopSimulation()
  runtimeModel.value = cloneGraphModel(props.model)
  if (runtimeModel.value.nodes.length === 0) {
    requestDraw()
    return
  }
  simulation = createLayeredForceSimulation(
    runtimeModel.value,
    canvasSize.value.width,
    canvasSize.value.height,
  )
  simulation.on('tick', requestDraw)
  if (shouldFit) {
    viewport.value = fitGraphToViewport(runtimeModel.value, canvasSize.value.width, canvasSize.value.height)
  }
  requestDraw()
}

function fitToView() {
  viewport.value = fitGraphToViewport(runtimeModel.value, canvasSize.value.width, canvasSize.value.height)
  requestDraw()
}

function reheatLayout() {
  simulation?.alpha(0.9).restart()
  requestDraw()
}

function pointerPoint(event: MouseEvent | PointerEvent | WheelEvent) {
  const rect = canvasRef.value?.getBoundingClientRect()
  return {
    x: event.clientX - (rect?.left ?? 0),
    y: event.clientY - (rect?.top ?? 0),
  }
}

function selectNode(node: KnowledgeGraphNode) {
  selectedNodeId.value = node.id
  emit('node-select', toNodeEvent(node))
  requestDraw()
}

function handleWheel(event: WheelEvent) {
  event.preventDefault()
  const point = pointerPoint(event)
  const world = screenToWorld(point, viewport.value)
  const zoomDelta = event.deltaY < 0 ? 1.12 : 0.89
  const nextScale = Math.min(2.8, Math.max(0.18, viewport.value.scale * zoomDelta))
  viewport.value = {
    x: point.x - world.x * nextScale,
    y: point.y - world.y * nextScale,
    scale: nextScale,
  }
  requestDraw()
}

function handlePointerDown(event: PointerEvent) {
  const canvas = canvasRef.value
  if (!canvas || event.button !== 0) {
    return
  }
  canvas.setPointerCapture(event.pointerId)
  activePointerId = event.pointerId
  pointerStart = pointerPoint(event)
  viewportStart = { ...viewport.value }
  movedDuringPointer = false
  const node = hitTestNode(runtimeModel.value, screenToWorld(pointerStart, viewport.value))
  if (node) {
    pointerMode = 'node'
    draggedNode = node
    node.fx = node.x ?? node.targetX
    node.fy = node.y ?? node.targetY
    simulation?.alphaTarget(0.22).restart()
    return
  }
  pointerMode = 'pan'
}

function handlePointerMove(event: PointerEvent) {
  const point = pointerPoint(event)
  const world = screenToWorld(point, viewport.value)
  if (pointerMode === 'node' && draggedNode && event.pointerId === activePointerId) {
    draggedNode.fx = world.x
    draggedNode.fy = world.y
    movedDuringPointer = true
    requestDraw()
    return
  }
  if (pointerMode === 'pan' && event.pointerId === activePointerId) {
    viewport.value = {
      ...viewport.value,
      x: viewportStart.x + point.x - pointerStart.x,
      y: viewportStart.y + point.y - pointerStart.y,
    }
    movedDuringPointer = true
    requestDraw()
    return
  }
  const nextHover = hitTestNode(runtimeModel.value, world)?.id ?? ''
  if (nextHover !== hoveredNodeId.value) {
    hoveredNodeId.value = nextHover
    requestDraw()
  }
}

function handlePointerUp(event: PointerEvent) {
  if (event.pointerId !== activePointerId) {
    return
  }
  const point = pointerPoint(event)
  const node = draggedNode ?? hitTestNode(runtimeModel.value, screenToWorld(point, viewport.value))
  if (draggedNode) {
    draggedNode.fx = null
    draggedNode.fy = null
    simulation?.alphaTarget(0)
  }
  if (node && !movedDuringPointer) {
    selectNode(node)
  }
  pointerMode = 'none'
  activePointerId = 0
  draggedNode = null
  requestDraw()
}

function handlePointerLeave() {
  if (pointerMode !== 'none') {
    return
  }
  hoveredNodeId.value = ''
  requestDraw()
}

function handleDoubleClick(event: MouseEvent) {
  const point = pointerPoint(event)
  const node = hitTestNode(runtimeModel.value, screenToWorld(point, viewport.value))
  if (!node) {
    fitToView()
    return
  }
  selectNode(node)
  viewport.value = focusNodeViewport(node, canvasSize.value.width, canvasSize.value.height, Math.max(0.95, viewport.value.scale))
  emit('node-open', toNodeEvent(node))
  requestDraw()
}

onMounted(() => {
  resizeObserver = new ResizeObserver(() => {
    resizeCanvas()
    startSimulation(false)
  })
  if (hostRef.value) {
    resizeObserver.observe(hostRef.value)
  }
  void nextTick(() => {
    resizeCanvas()
    startSimulation()
  })
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  resizeObserver = null
  stopSimulation()
  if (animationFrame) {
    window.cancelAnimationFrame(animationFrame)
  }
})

watch(
  () => props.model,
  () => startSimulation(),
)

watch(
  () => props.selectedNodeId,
  (value) => {
    selectedNodeId.value = value ?? ''
    requestDraw()
  },
)

defineExpose({
  fitToView,
  reheatLayout,
  graphStats,
})
</script>

<template>
  <div ref="hostRef" class="knowledge-graph-canvas">
    <canvas
      ref="canvasRef"
      :class="{ hovering: hoveredNodeId }"
      aria-label="Knowledge graph canvas"
      @dblclick="handleDoubleClick"
      @pointerdown="handlePointerDown"
      @pointermove="handlePointerMove"
      @pointerup="handlePointerUp"
      @pointercancel="handlePointerUp"
      @pointerleave="handlePointerLeave"
      @wheel="handleWheel"
    ></canvas>
  </div>
</template>

<style scoped>
.knowledge-graph-canvas {
  position: relative;
  width: 100%;
  height: 100%;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  background: var(--color-canvas-soft);
}

canvas {
  display: block;
  width: 100%;
  height: 100%;
  cursor: grab;
  touch-action: none;
}

canvas:active {
  cursor: grabbing;
}

canvas.hovering {
  cursor: pointer;
}
</style>
