import { apiGet, apiPost } from '@/api/client'
import { API_ROUTES } from '@/router/api_routes'

export interface AutomationTaskData {
  id: string
  todoId: string
  prompt: string
  timezone: string
  recurrence: { frequency: 'none' | 'daily' | 'weekly' | 'monthly'; interval: number }
  nextRunAt: string
  accessMode: 'readonly' | 'sandbox' | 'full_access'
  enabled: boolean
  lastRunAt?: string | null
  lastStatus?: 'success' | 'failed' | 'skipped' | null
  lastError?: string | null
}

export interface AutomationRunData {
  id: string
  automationId: string
  userId: string
  status: 'running' | 'success' | 'failed' | 'skipped'
  startedAt: string
  finishedAt?: string | null
  output?: string | null
  error?: string | null
}

export function apiListAutomations(userId: string): Promise<AutomationTaskData[]> {
  return apiGet(API_ROUTES.AUTOMATION_LIST, { user_id: userId })
}

export function apiAddAutomation(
  userId: string,
  text: string,
  prompt: string,
  nextRunAt: string,
  timezone: string,
  recurrence: AutomationTaskData['recurrence'],
  accessMode: AutomationTaskData['accessMode'],
): Promise<AutomationTaskData> {
  return apiPost(API_ROUTES.AUTOMATION_ADD, {
    user_id: userId,
    text,
    prompt,
    next_run_at: nextRunAt,
    timezone,
    recurrence,
    access_mode: accessMode,
  })
}

export function apiToggleAutomation(userId: string, automationId: string, enabled: boolean): Promise<AutomationTaskData> {
  return apiPost(API_ROUTES.AUTOMATION_TOGGLE, { user_id: userId, automation_id: automationId, enabled })
}

export function apiDeleteAutomation(userId: string, automationId: string): Promise<{ deleted: boolean }> {
  return apiPost(API_ROUTES.AUTOMATION_DELETE, { user_id: userId, automation_id: automationId })
}

export function apiListAutomationRuns(
  userId: string,
  automationId: string,
  limit = 20,
): Promise<AutomationRunData[]> {
  return apiGet(API_ROUTES.AUTOMATION_RUNS, {
    user_id: userId,
    automation_id: automationId,
    limit,
  })
}
