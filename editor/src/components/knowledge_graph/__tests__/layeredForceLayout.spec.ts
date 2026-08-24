/*
 * Knowledge graph force-layout regression tests.
 *
 * Usage:
 * Run with Vitest to verify that all four graph views share semantic physics
 * and that semantic neighbours stay local during drag.
 */

import { describe, expect, it } from 'vitest'

import { createLayeredForceSimulation } from '../layeredForceLayout'
import type { KnowledgeGraphModel, KnowledgeGraphNode } from '../graphTypes'

/** Creates a deterministic graph node for force-only tests. */
function node(id: string, kind: KnowledgeGraphNode['kind'], x: number, y: number): KnowledgeGraphNode {
  return {
    id, label: id, path: kind === 'document' ? `${id}.md` : '', kind,
    depth: 0, siblingIndex: 0, siblingCount: 1, ringIndex: 0,
    radius: kind === 'document' ? 8 : 5, targetX: x, targetY: y, x, y,
  }
}

/** Builds a backlink star containing only peer document nodes. */
function backlinkGraph(): KnowledgeGraphModel {
  const nodes = Array.from({ length: 9 }, (_, index) => {
    const angle = (index / 9) * Math.PI * 2
    return node(`document-${index}`, 'document', 400 + Math.cos(angle) * 120, 300 + Math.sin(angle) * 120)
  })
  return {
    nodes,
    links: nodes.slice(1).map((target, index) => ({
      id: `reference-${index}`, source: nodes[0]!.id, target: target.id, kind: 'reference', weight: 1,
    })),
  }
}

/** Builds the minimal parent-child topology used by the file-tree graph. */
function fileTreeGraph(): KnowledgeGraphModel {
  const root = node('root', 'root', 0, 0)
  const child = { ...node('folder', 'folder', 40, 0), parentId: root.id, depth: 1 }
  return {
    nodes: [root, child],
    links: [{ id: 'tree-link', source: root.id, target: child.id, kind: 'parent-child' }],
  }
}

/** Builds the minimal parent-child topology used by the library graph. */
function libraryGraph(): KnowledgeGraphModel {
  const root = node('library', 'library', 0, 0)
  const child = { ...node('book', 'file', 40, 0), parentId: root.id, depth: 1 }
  return {
    nodes: [root, child],
    links: [{ id: 'library-link', source: root.id, target: child.id, kind: 'parent-child' }],
  }
}

/** Builds one semantic document with evenly seeded entity neighbours. */
function semanticStar(documentX: number, documentY: number): KnowledgeGraphModel {
  const document = node('document', 'document', documentX, documentY)
  const entities = Array.from({ length: 10 }, (_, index) => {
    const angle = (index / 10) * Math.PI * 2
    return node(`entity-${index}`, 'entity', documentX + Math.cos(angle) * 64, documentY + Math.sin(angle) * 64)
  })
  return {
    nodes: [document, ...entities],
    links: entities.map((entity, index) => ({
      id: `semantic-${index}`, source: document.id, target: entity.id, kind: 'semantic', weight: 1,
    })),
  }
}

/** Settles a semantic star while its document is held at a drag position. */
function settleDraggedStar(documentX: number, documentY: number) {
  const model = semanticStar(documentX, documentY)
  const document = model.nodes[0]!
  document.fx = documentX
  document.fy = documentY
  const simulation = createLayeredForceSimulation(model, 800, 600).stop()
  simulation.tick(300)
  const offsets = model.nodes.slice(1).map((entity) => ({
    x: (entity.x ?? 0) - (document.x ?? 0), y: (entity.y ?? 0) - (document.y ?? 0),
  }))
  const meanRadius = offsets.reduce((sum, offset) => sum + Math.hypot(offset.x, offset.y), 0) / offsets.length
  const centroidOffset = Math.hypot(
    offsets.reduce((sum, offset) => sum + offset.x, 0) / offsets.length,
    offsets.reduce((sum, offset) => sum + offset.y, 0) / offsets.length,
  )
  return { simulation, meanRadius, centroidOffset }
}

/** Returns the mean distance across every node pair in one set. */
function meanPairwiseDistance(nodes: KnowledgeGraphNode[]) {
  let distance = 0
  let pairs = 0
  for (let left = 0; left < nodes.length; left++) {
    for (let right = left + 1; right < nodes.length; right++) {
      distance += Math.hypot(
        (nodes[left]!.x ?? 0) - (nodes[right]!.x ?? 0),
        (nodes[left]!.y ?? 0) - (nodes[right]!.y ?? 0),
      )
      pairs += 1
    }
  }
  return distance / pairs
}

describe('createLayeredForceSimulation', () => {
  it.each([
    ['semantic', () => semanticStar(400, 300)],
    ['file tree', fileTreeGraph],
    ['library', libraryGraph],
    ['backlink', backlinkGraph],
  ])('uses the semantic force contract for the %s graph', (_name, buildModel) => {
    const simulation = createLayeredForceSimulation(buildModel(), 800, 600).stop()

    expect(simulation.alpha()).toBe(0.12)
    expect(simulation.alphaDecay()).toBe(0)
    expect(simulation.alphaMin()).toBe(0)
    expect(simulation.velocityDecay()).toBe(0.48)
    expect(simulation.force('link')).toBeTypeOf('function')
    expect(simulation.force('charge')).toBeTypeOf('function')
    expect(simulation.force('collide')).toBeTypeOf('function')
    expect(simulation.force('document-repulsion')).toBeTypeOf('function')
    expect(simulation.force('x')).toBeUndefined()
    expect(simulation.force('y')).toBeUndefined()
    expect(simulation.force('center')).toBeUndefined()
  })

  it('keeps semantic neighbours locally balanced during an off-center document drag', () => {
    const centered = settleDraggedStar(400, 300)
    const offCenter = settleDraggedStar(680, 300)

    expect(offCenter.simulation.alphaDecay()).toBe(0)
    expect(offCenter.simulation.force('center')).toBeUndefined()
    expect(centered.centroidOffset / centered.meanRadius).toBeLessThan(0.25)
    expect(offCenter.centroidOffset / offCenter.meanRadius).toBeLessThan(0.25)
    expect(offCenter.meanRadius / centered.meanRadius).toBeGreaterThan(0.8)
    expect(offCenter.meanRadius / centered.meanRadius).toBeLessThan(1.2)
  })

  it('does not globally expand untouched nodes while one semantic node is held outward', () => {
    const model = semanticStar(400, 300)
    const simulation = createLayeredForceSimulation(model, 800, 600).stop()
    simulation.tick(300)
    const dragged = model.nodes[1]!
    const untouched = model.nodes.filter((item) => item !== dragged)
    const spreadBefore = meanPairwiseDistance(untouched)

    dragged.fx = (dragged.x ?? 0) + 240
    dragged.fy = dragged.y
    simulation.alpha(Math.max(simulation.alpha(), 0.12)).tick(90)

    expect(simulation.alphaTarget()).toBe(0)
    expect(meanPairwiseDistance(untouched) / spreadBefore).toBeLessThan(1.2)
  })
})
