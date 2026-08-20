/** Workspace graph-extraction prerequisite and re-extraction decision tests. */

import { describe, expect, it } from 'vitest'

import { graphIngestionTargets, shouldForceGraphExtraction } from '@/stores/workspace'
import type { KnowledgeFileNode } from '@/types/knowledge'

describe('workspace graph extraction decisions', () => {
  it('reuses an indexed file and forces only an already graphed file', () => {
    const indexed: KnowledgeFileNode = {
      name: 'notes.md', path: 'notes.md', isDir: false, indexStatus: 'indexed', graphStatus: 'dirty',
    }
    const graphed: KnowledgeFileNode = { ...indexed, graphStatus: 'graphed' }

    expect(graphIngestionTargets(indexed)).toEqual([])
    expect(shouldForceGraphExtraction(indexed)).toBe(false)
    expect(graphIngestionTargets(graphed)).toEqual([])
    expect(shouldForceGraphExtraction(graphed)).toBe(true)
  })

  it('ingests only dirty descendants before extracting a folder graph', () => {
    const indexed: KnowledgeFileNode = {
      name: 'ready.md', path: 'docs/ready.md', isDir: false, indexStatus: 'indexed', graphStatus: 'dirty',
    }
    const dirty: KnowledgeFileNode = {
      name: 'draft.md', path: 'docs/draft.md', isDir: false, indexStatus: 'dirty', graphStatus: 'dirty',
    }
    const folder: KnowledgeFileNode = {
      name: 'docs', path: 'docs', isDir: true, children: [indexed, dirty],
    }

    expect(graphIngestionTargets(folder)).toEqual([dirty])
  })
})
