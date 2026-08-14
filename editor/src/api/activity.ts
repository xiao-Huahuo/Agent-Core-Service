/*
 * Daily activity heatmap API client.
 *
 * Usage:
 * Dashboard components call `fetchActivityHeatmap` once per user and derive all
 * category filters from the persisted 53-week response.
 */

import { apiGet } from '@/api/client'
import { API_ROUTES } from '@/router/api_routes'

export type ActivityModule = 'library' | 'documents' | 'knowledge' | 'agent' | 'tasks' | 'other'
export type ActivityFilter = 'all' | ActivityModule

export interface ActivitySummary {
  total_score: number
  active_days: number
  current_streak: number
  peak_score: number
}

export interface ActivityDetail {
  module: ActivityModule
  action: string
  score: number
  title: string
  created_at: string
}

export interface ActivityDay {
  date: string
  score: number
  level: number
  event_count: number
  modules: Partial<Record<ActivityModule, { score: number; event_count: number }>>
  activities: ActivityDetail[]
}

export interface ActivityHeatmapResponse {
  timezone: string
  start_date: string
  end_date: string
  days: ActivityDay[]
  summaries: Record<ActivityFilter, ActivitySummary>
}

/** Fetch the persisted 53-week activity dataset for one user. */
export function fetchActivityHeatmap(
  userId: string,
  timezone = 'Asia/Shanghai',
): Promise<ActivityHeatmapResponse> {
  return apiGet<ActivityHeatmapResponse>(API_ROUTES.ACTIVITY_HEATMAP, {
    user_id: userId,
    days: 364,
    timezone,
  }, {
    // The first request may idempotently backfill years of existing records.
    timeoutMs: 120_000,
  })
}
