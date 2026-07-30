/*
 * Token usage display aggregation tests.
 *
 * Usage:
 * Locks the totals shown in the dashboard card header to the exact rows
 * rendered by each chart tab.
 */

import { describe, expect, it } from 'vitest'

import { buildTokenViewTotals, formatTokenModelLabel } from '../useTokenUsageDisplay'

describe('buildTokenViewTotals', () => {
  const stats = {
    interval: '5m' as const,
    calls: [
      { model_tier: 'large', total_tokens: 10 },
      { model_tier: 'small', total_tokens: 4 },
    ],
    buckets: [
      { large_tokens: 20, small_tokens: 5 },
      { large_tokens: 30, small_tokens: 0 },
    ],
    sessions: [
      { total_tokens: 12, large_tokens: 7, small_tokens: 5 },
      { total_tokens: 0, large_tokens: 0, small_tokens: 0 },
    ],
  }

  it('totals the rows rendered by each active tab', () => {
    expect(buildTokenViewTotals(stats, 'calls')).toEqual({ large: 10, small: 4 })
    expect(buildTokenViewTotals(stats, 'buckets')).toEqual({ large: 50, small: 5 })
    expect(buildTokenViewTotals(stats, 'sessions')).toEqual({ large: 7, small: 5 })
  })

  it('marks configured model names with their model tier', () => {
    expect(formatTokenModelLabel('deepseek-chat', 'large')).toBe('deepseek-chat（大模型）')
    expect(formatTokenModelLabel('', 'small')).toBe('小模型')
  })
})
