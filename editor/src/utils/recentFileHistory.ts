/*
 * Recent file history helpers.
 *
 * Usage:
 * Keeps file visits unique and builds the date sections displayed by the
 * recent-files mode in the workspace file tree.
 */
import type { KnowledgeFileNode } from '@/types/knowledge'

export interface RecentFileVisit {
  /** Knowledge-root-relative file path. */
  path: string
  /** ISO timestamp of the latest recorded visit. */
  lastViewedAt: string
}

export interface RecentFileItem {
  /** Current file-tree node associated with the stored path. */
  node: KnowledgeFileNode
  /** ISO timestamp shown in the recent card. */
  lastViewedAt: string
}

export interface RecentFileGroup {
  /** Stable internal section identifier. */
  key: 'today' | 'yesterday' | 'this-week' | 'last-week' | 'this-month' | 'this-year' | 'older'
  /** Localized section heading. */
  label: '今天' | '昨天' | '本周' | '上周' | '本月' | '今年' | '更早'
  /** Recent files assigned exclusively to this section. */
  items: RecentFileItem[]
}

/** Maximum visits retained for one user and knowledge root. */
export const RECENT_FILE_HISTORY_LIMIT = 500

/** Moves a viewed path to the front while preserving one record per file. */
export function updateRecentFileVisits(
  visits: RecentFileVisit[],
  path: string,
  lastViewedAt: string,
): RecentFileVisit[] {
  return [
    { path, lastViewedAt },
    ...visits.filter((visit) => visit.path !== path),
  ].slice(0, RECENT_FILE_HISTORY_LIMIT)
}

/** Resolves stored visits against current files, filters by name, and groups by local date. */
export function buildRecentFileGroups(
  visits: RecentFileVisit[],
  nodes: KnowledgeFileNode[],
  query: string,
  now = new Date(),
): RecentFileGroup[] {
  const nodeByPath = new Map(nodes.filter((node) => !node.isDir).map((node) => [node.path, node]))
  const normalizedQuery = query.trim().toLocaleLowerCase()
  const startToday = startOfDay(now)
  const startYesterday = addDays(startToday, -1)
  const startWeek = startOfWeek(startToday)
  const startLastWeek = addDays(startWeek, -7)
  const startMonth = new Date(now.getFullYear(), now.getMonth(), 1)
  const startYear = new Date(now.getFullYear(), 0, 1)
  const groups: RecentFileGroup[] = [
    { key: 'today', label: '今天', items: [] },
    { key: 'yesterday', label: '昨天', items: [] },
    { key: 'this-week', label: '本周', items: [] },
    { key: 'last-week', label: '上周', items: [] },
    { key: 'this-month', label: '本月', items: [] },
    { key: 'this-year', label: '今年', items: [] },
    { key: 'older', label: '更早', items: [] },
  ]

  visits
    .map((visit) => ({ visit, timestamp: new Date(visit.lastViewedAt).getTime() }))
    .filter(({ visit, timestamp }) => {
      const node = nodeByPath.get(visit.path)
      return Boolean(node)
        && Number.isFinite(timestamp)
        && (!normalizedQuery || node!.name.toLocaleLowerCase().includes(normalizedQuery))
    })
    .sort((a, b) => b.timestamp - a.timestamp)
    .forEach(({ visit, timestamp }) => {
      const node = nodeByPath.get(visit.path)
      if (!node) return
      const groupIndex = timestamp >= startToday.getTime()
        ? 0
        : timestamp >= startYesterday.getTime()
          ? 1
          : timestamp >= startWeek.getTime()
            ? 2
            : timestamp >= startLastWeek.getTime()
              ? 3
              : timestamp >= startMonth.getTime()
                ? 4
                : timestamp >= startYear.getTime()
                  ? 5
                  : 6
      groups[groupIndex]?.items.push({ node, lastViewedAt: visit.lastViewedAt })
    })

  return groups.filter((group) => group.items.length > 0)
}

/** Returns the parent directory label shown below a recent filename. */
export function recentFileParentPath(path: string): string {
  const parts = path.replace(/\\/g, '/').split('/').filter(Boolean)
  parts.pop()
  return parts.join('/') || '根目录'
}

/** Detects files eligible for a lazy thumbnail preview. */
export function isImageFilePath(path: string): boolean {
  return /\.(?:avif|bmp|gif|ico|jpe?g|png|svg|webp)$/i.test(path)
}

/** Returns local midnight for the supplied date. */
function startOfDay(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate())
}

/** Returns local Monday midnight for the supplied date's week. */
function startOfWeek(date: Date): Date {
  const mondayOffset = (date.getDay() + 6) % 7
  return addDays(date, -mondayOffset)
}

/** Adds local calendar days without mutating the supplied date. */
function addDays(date: Date, amount: number): Date {
  const result = new Date(date)
  result.setDate(result.getDate() + amount)
  return result
}
