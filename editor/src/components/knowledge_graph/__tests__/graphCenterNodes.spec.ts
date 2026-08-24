/*
 * Knowledge graph artificial-center regression tests.
 *
 * Usage:
 * Run with Vitest to ensure semantic and library adapters expose only real
 * backend/user nodes while preserving real nested library relationships.
 */

import { describe, expect, it } from 'vitest'

import { buildLibraryGraph } from '../libraryGraphAdapter'
import { buildSemanticKnowledgeGraph } from '../semanticGraphAdapter'
import type { KnowledgeSemanticGraphResponse, LibraryItem } from '@/types/knowledge'

/** Creates the fields consumed by the library graph adapter. */
function libraryItem(id: string, type: 'book' | 'collection', parentId = ''): LibraryItem {
  return {
    item_id: id,
    parent_id: parentId,
    item_type: type,
    display_title: id,
    source_name: type === 'book' ? `${id}.md` : '',
    source_path: type === 'book' ? `${id}.md` : '',
  } as LibraryItem
}

describe('graph adapters without artificial centers', () => {
  it('keeps only backend semantic nodes and links', () => {
    const payload: KnowledgeSemanticGraphResponse = {
      nodes: [
        { id: 'document', label: '文档', kind: 'document' },
        { id: 'entity', label: '实体', kind: 'entity' },
      ],
      links: [{ id: 'relation', source: 'document', target: 'entity', kind: 'semantic' }],
      stats: {},
    }

    const model = buildSemanticKnowledgeGraph(payload)

    expect(model.nodes.map((node) => node.id)).toEqual(['document', 'entity'])
    expect(model.links.map((link) => link.id)).toEqual(['relation'])
  })

  it('keeps top-level library items rootless and only links real nesting', () => {
    const model = buildLibraryGraph([
      libraryItem('collection', 'collection'),
      libraryItem('nested-book', 'book', 'collection'),
      libraryItem('top-book', 'book'),
    ])

    expect(model.nodes.map((node) => node.id).sort()).toEqual([
      'library-book:nested-book',
      'library-book:top-book',
      'library:collection',
    ])
    expect(model.links).toHaveLength(1)
    expect(model.links[0]).toMatchObject({
      source: 'library:collection',
      target: 'library-book:nested-book',
    })
  })
})
