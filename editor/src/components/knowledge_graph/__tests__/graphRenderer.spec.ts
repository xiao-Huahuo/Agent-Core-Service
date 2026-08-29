/*
 * Knowledge graph Canvas renderer regression tests.
 *
 * Usage:
 * Run this focused Vitest file to verify zoom-dependent graph presentation
 * without mounting the Vue shell or starting a browser.
 */

import { describe, expect, it, vi } from 'vitest'

import { drawKnowledgeGraph } from '../graphRenderer'
import type {
  KnowledgeGraphModel,
  KnowledgeGraphRenderState,
  KnowledgeGraphRenderTheme,
} from '../graphTypes'

/** Creates the smallest Canvas 2D spy required by the graph renderer. */
function createCanvasContext() {
  return {
    arc: vi.fn(),
    beginPath: vi.fn(),
    clearRect: vi.fn(),
    clip: vi.fn(),
    fill: vi.fn(),
    fillRect: vi.fn(),
    fillText: vi.fn(),
    lineTo: vi.fn(),
    moveTo: vi.fn(),
    restore: vi.fn(),
    save: vi.fn(),
    scale: vi.fn(),
    setLineDash: vi.fn(),
    stroke: vi.fn(),
    translate: vi.fn(),
  } as unknown as CanvasRenderingContext2D
}

const model: KnowledgeGraphModel = {
  nodes: [
    {
      id: 'root',
      label: '知识库',
      path: '',
      kind: 'root',
      depth: 0,
      siblingIndex: 0,
      siblingCount: 1,
      ringIndex: 0,
      radius: 18,
      targetX: 50,
      targetY: 50,
    },
  ],
  links: [],
}

const theme: KnowledgeGraphRenderTheme = {
  isDark: true,
  canvas: '#111111',
  grid: 'rgba(255,255,255,0.04)',
  text: '#ffffff',
  mutedText: '#999999',
  edge: 'rgba(255,255,255,0.2)',
  edgeActive: '#4224eb',
  root: '#4224eb',
  folder: '#4224eb',
  file: '#cccccc',
  selected: '#eb2463',
  accent: '#eb2463',
  surface: '#202026',
}

/** Creates renderer state at the requested graph zoom. */
function stateAtScale(scale: number): KnowledgeGraphRenderState {
  return {
    viewport: { x: 0, y: 0, scale },
    hoveredNodeId: 'root',
    selectedNodeId: 'root',
    showLabels: true,
  }
}

describe('knowledge graph compact rendering', () => {
  it('hides every label while the graph is strongly zoomed out', () => {
    const context = createCanvasContext()

    drawKnowledgeGraph(context, model, stateAtScale(0.55), theme, 100, 100)

    expect(context.fillText).not.toHaveBeenCalled()
  })

  it('keeps labels at a readable graph scale', () => {
    const context = createCanvasContext()

    drawKnowledgeGraph(context, model, stateAtScale(1), theme, 100, 100)

    expect(context.fillText).toHaveBeenCalledWith('知识库', 50, 75)
  })
})
