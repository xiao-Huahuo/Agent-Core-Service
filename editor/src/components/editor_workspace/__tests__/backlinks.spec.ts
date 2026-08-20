import { describe, expect, it } from 'vitest'

import { buildBacklinks } from '../backlinks'
import type { KnowledgeFileNode } from '@/types/knowledge'

const tree: KnowledgeFileNode[] = [
  { name: 'Target.md', path: 'notes/Target.md', isDir: false },
  { name: 'Source.md', path: 'notes/Source.md', isDir: false },
  { name: 'Other.md', path: 'Other.md', isDir: false },
]

describe('buildBacklinks', () => {
  it('groups incoming links by source and preserves article and heading spellings', () => {
    const entries = buildBacklinks('notes/Target.md', tree, {
      'notes/Source.md': '整篇 [[Target]]\n标题 [[Target#安装|安装章节]]',
      'Other.md': '块 [[notes/Target#^block-1]]',
      'notes/Target.md': '无关 [[Other]]',
    })

    expect(entries).toEqual([
      {
        path: 'Other.md',
        name: 'Other.md',
        occurrences: [{ raw: '[[notes/Target#^block-1]]', targetKind: 'block', targetLabel: 'block-1' }],
      },
      {
        path: 'notes/Source.md',
        name: 'Source.md',
        occurrences: [
          { raw: '[[Target]]', targetKind: 'article', targetLabel: '' },
          { raw: '[[Target#安装|安装章节]]', targetKind: 'heading', targetLabel: '安装' },
        ],
      },
    ])
  })

  it('does not include unresolved or differently targeted wiki links', () => {
    expect(buildBacklinks('notes/Target.md', tree, {
      'notes/Source.md': '[[Missing]] [[Other]]',
    })).toEqual([])
  })
})
