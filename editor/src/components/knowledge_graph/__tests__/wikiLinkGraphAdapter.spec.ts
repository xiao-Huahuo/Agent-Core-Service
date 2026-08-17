/*
 * Bidirectional wiki-link graph adapter tests.
 *
 * Usage:
 * Locks the graph contract for normal [[...]] references, ![[...]] embeds,
 * aliases, headings, duplicate occurrences, unresolved targets, and assets.
 */

import { describe, expect, it } from 'vitest'

import type { KnowledgeFileNode } from '@/types/knowledge'
import { buildWikiLinkGraph } from '../wikiLinkGraphAdapter'

const tree: KnowledgeFileNode[] = [{
  name: 'notes',
  path: 'notes',
  isDir: true,
  children: [
    { name: 'source.md', path: 'notes/source.md', isDir: false },
    { name: 'target.md', path: 'notes/target.md', isDir: false },
    { name: 'other.md', path: 'notes/other.md', isDir: false },
    { name: 'chart.png', path: 'notes/static/chart.png', isDir: false },
  ],
}]

describe('buildWikiLinkGraph', () => {
  it('aggregates every resolved reference and embed occurrence by kind', () => {
    const graph = buildWikiLinkGraph(tree, {
      'notes/source.md': [
        '[[target]] [[target#章节|别名]]',
        '![[target#摘要]] ![[static/chart.png]]',
        '[[missing]] `[[other]]`',
      ].join('\n'),
      'notes/target.md': '反向指回 [[source]]',
      'notes/other.md': '没有链接',
    })

    expect(graph.nodes.map((node) => node.path)).toEqual([
      'notes/other.md',
      'notes/source.md',
      'notes/static/chart.png',
      'notes/target.md',
    ])
    expect(graph.links).toEqual(expect.arrayContaining([
      expect.objectContaining({ source: 'notes/source.md', target: 'notes/target.md', kind: 'reference', weight: 2 }),
      expect.objectContaining({ source: 'notes/source.md', target: 'notes/target.md', kind: 'embed', weight: 1 }),
      expect.objectContaining({ source: 'notes/source.md', target: 'notes/static/chart.png', kind: 'embed', weight: 1 }),
      expect.objectContaining({ source: 'notes/target.md', target: 'notes/source.md', kind: 'reference', weight: 1 }),
    ]))
    expect(graph.links).toHaveLength(4)
  })

  it('keeps every Markdown document as a navigable node even when isolated', () => {
    const graph = buildWikiLinkGraph(tree, {
      'notes/source.md': '',
      'notes/target.md': '',
      'notes/other.md': '',
    })

    expect(graph.nodes).toHaveLength(3)
    expect(graph.nodes.every((node) => node.kind === 'document' && node.path.endsWith('.md'))).toBe(true)
    expect(graph.links).toEqual([])
  })
})
