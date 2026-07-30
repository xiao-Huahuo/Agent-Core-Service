/*
 * Token usage dashboard display helpers.
 *
 * Usage:
 * TokenUsageCard uses these pure helpers to keep its header totals aligned
 * with the rows rendered by the active calls, buckets, or sessions chart.
 */

export type TokenChartKind = 'buckets' | 'calls' | 'sessions'
export type TokenModelTier = 'large' | 'small'

interface TokenDisplayStats {
  calls: Array<{ model_tier: string; total_tokens: number }>
  buckets: Array<{ large_tokens: number; small_tokens: number }>
  sessions: Array<{ total_tokens: number; large_tokens: number; small_tokens: number }>
}

/** Return the non-empty session rows that the chart displays. */
export function displayedTokenSessions<T extends { total_tokens: number }>(sessions: T[]): T[] {
  return sessions.filter((session) => session.total_tokens > 0).slice(0, 12)
}

/** Sum large and small tokens from exactly the rows rendered by one chart tab. */
export function buildTokenViewTotals(
  stats: TokenDisplayStats,
  kind: TokenChartKind,
): { large: number; small: number } {
  if (kind === 'calls') {
    return stats.calls.reduce((totals, call) => {
      if (call.model_tier === 'large') totals.large += call.total_tokens
      if (call.model_tier === 'small') totals.small += call.total_tokens
      return totals
    }, { large: 0, small: 0 })
  }
  if (kind === 'buckets') {
    return stats.buckets.reduce((totals, bucket) => ({
      large: totals.large + bucket.large_tokens,
      small: totals.small + bucket.small_tokens,
    }), { large: 0, small: 0 })
  }
  return displayedTokenSessions(stats.sessions).reduce((totals, session) => ({
    large: totals.large + session.large_tokens,
    small: totals.small + session.small_tokens,
  }), { large: 0, small: 0 })
}

/** Format a configured provider model name and identify its scheduler tier. */
export function formatTokenModelLabel(modelName: string, tier: TokenModelTier): string {
  const normalizedName = modelName.trim()
  if (!normalizedName) return tier === 'large' ? '大模型' : '小模型'
  return `${normalizedName}（${tier === 'large' ? '大模型' : '小模型'}）`
}
