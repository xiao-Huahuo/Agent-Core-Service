/*
 * Recent file history utilities tests.
 *
 * Usage:
 * Verifies visit de-duplication, filename filtering, and mutually exclusive
 * local-date grouping for the recent-files view.
 */
import { describe, expect, it } from 'vitest'

import type { KnowledgeFileNode } from '@/types/knowledge'
import {
  buildRecentFileGroups,
  updateRecentFileVisits,
  type RecentFileVisit,
} from '@/utils/recentFileHistory'

function file(path: string): KnowledgeFileNode {
  const parts = path.split('/')
  return {
    name: parts[parts.length - 1] ?? path,
    path,
    isDir: false,
    indexStatus: 'indexed',
    graphStatus: 'graphed',
  }
}

describe('recent file history', () => {
  it('moves a revisited path to the front and keeps one record per file', () => {
    const visits: RecentFileVisit[] = [
      { path: 'docs/a.md', lastViewedAt: '2026-07-28T09:00:00.000Z' },
      { path: 'docs/b.md', lastViewedAt: '2026-07-27T09:00:00.000Z' },
    ]

    expect(updateRecentFileVisits(visits, 'docs/b.md', '2026-07-30T09:00:00.000Z')).toEqual([
      { path: 'docs/b.md', lastViewedAt: '2026-07-30T09:00:00.000Z' },
      { path: 'docs/a.md', lastViewedAt: '2026-07-28T09:00:00.000Z' },
    ])
  })

  it('filters missing files and partially matches the filename case-insensitively', () => {
    const visits: RecentFileVisit[] = [
      { path: 'docs/Project-Plan.md', lastViewedAt: '2026-07-30T09:00:00+08:00' },
      { path: 'images/cover.png', lastViewedAt: '2026-07-30T08:00:00+08:00' },
      { path: 'deleted.txt', lastViewedAt: '2026-07-30T07:00:00+08:00' },
    ]
    const nodes = [file('docs/Project-Plan.md'), file('images/cover.png')]

    const groups = buildRecentFileGroups(visits, nodes, 'PLAN', new Date(2026, 6, 30, 12))

    expect(groups.flatMap((group) => group.items).map((item) => item.node.path)).toEqual([
      'docs/Project-Plan.md',
    ])
  })

  it('groups dates without overlap using Monday as the start of the week', () => {
    const visits: RecentFileVisit[] = [
      { path: 'today.md', lastViewedAt: new Date(2026, 6, 30, 9).toISOString() },
      { path: 'yesterday.md', lastViewedAt: new Date(2026, 6, 29, 9).toISOString() },
      { path: 'this-week.md', lastViewedAt: new Date(2026, 6, 28, 9).toISOString() },
      { path: 'last-week.md', lastViewedAt: new Date(2026, 6, 22, 9).toISOString() },
      { path: 'this-month.md', lastViewedAt: new Date(2026, 6, 5, 9).toISOString() },
      { path: 'this-year.md', lastViewedAt: new Date(2026, 1, 5, 9).toISOString() },
      { path: 'older.md', lastViewedAt: new Date(2025, 11, 5, 9).toISOString() },
    ]
    const nodes = visits.map((visit) => file(visit.path))

    const groups = buildRecentFileGroups(visits, nodes, '', new Date(2026, 6, 30, 12))

    expect(groups.map((group) => [group.label, group.items.map((item) => item.node.path)])).toEqual([
      ['今天', ['today.md']],
      ['昨天', ['yesterday.md']],
      ['本周', ['this-week.md']],
      ['上周', ['last-week.md']],
      ['本月', ['this-month.md']],
      ['今年', ['this-year.md']],
      ['更早', ['older.md']],
    ])
  })
})
