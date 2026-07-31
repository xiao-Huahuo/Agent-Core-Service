/*
 * Git push file-tree builder tests.
 *
 * Usage:
 * Ensures the push preview groups changed files by relative directory instead
 * of rendering the backend's flat name-status list.
 */

import { describe, expect, it } from 'vitest'

import { buildGitPushTree } from '@/components/git_sidebar/gitPushTree'

describe('buildGitPushTree', () => {
  it('groups files into sorted relative-directory nodes', () => {
    const tree = buildGitPushTree([
      { path: 'notes/topic/b.md', status: 'M' },
      { path: 'README.md', status: 'A' },
      { path: 'notes/a.md', status: 'D' },
    ])

    expect(tree.map((node) => node.name)).toEqual(['notes', 'README.md'])
    expect(tree[0]?.children.map((node) => node.name)).toEqual(['topic', 'a.md'])
    expect(tree[0]?.children[0]?.children[0]).toMatchObject({
      name: 'b.md',
      path: 'notes/topic/b.md',
      status: 'M',
      directory: false,
    })
  })
})
