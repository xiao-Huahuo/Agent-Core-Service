import { apiGet, apiPost } from '@/api/client'
import { API_ROUTES } from '@/router/api_routes'

export interface AgentTaskListItem {
  id: string
  title: string
  status: 'pending' | 'in_progress' | 'completed'
  completion_summary?: string
  completed_at?: string | null
}

export interface AgentTaskList {
  task_list_id: string
  session_id: string
  title: string
  status: 'active' | 'completed'
  current_item_id?: string | null
  items: AgentTaskListItem[]
  final_summary?: string
  created_at?: string
  updated_at?: string
  completed_at?: string | null
}

export interface TaskListResponse {
  task_list: AgentTaskList | null
}

export function fetchSessionTaskList(sessionId: string): Promise<TaskListResponse> {
  return apiGet<TaskListResponse>(API_ROUTES.SESSION_TASK_LIST(sessionId))
}

export function createSessionTaskList(
  sessionId: string,
  title: string,
  items: string[],
): Promise<TaskListResponse> {
  return apiPost<TaskListResponse>(API_ROUTES.SESSION_TASK_LIST(sessionId), { title, items })
}

export function completeSessionTaskListItem(
  sessionId: string,
  itemId: string,
  completionSummary: string,
  nextItemId?: string,
): Promise<TaskListResponse> {
  return apiPost<TaskListResponse>(API_ROUTES.SESSION_TASK_LIST_COMPLETE_ITEM(sessionId), {
    item_id: itemId,
    completion_summary: completionSummary,
    next_item_id: nextItemId,
  })
}

export function finishSessionTaskList(sessionId: string, finalSummary = ''): Promise<TaskListResponse> {
  return apiPost<TaskListResponse>(API_ROUTES.SESSION_TASK_LIST_FINISH(sessionId), {
    final_summary: finalSummary,
  })
}
