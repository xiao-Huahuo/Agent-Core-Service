import { apiGet, apiPost } from '@/api/client'
import { API_ROUTES } from '@/router/api_routes'

export interface TodoItemData {
  id: string
  text: string
  category?: string
  done: boolean
  createdAt: string
  updatedAt?: string
  dueDate?: string
  reminderAt?: string
  recurrence?: { frequency: 'none' | 'daily' | 'weekly' | 'monthly'; interval: number }
  lastCompletedAt?: string
}

export function apiListTodos(userId: string): Promise<TodoItemData[]> {
  return apiGet(API_ROUTES.TODO_LIST, { user_id: userId })
}

export function apiAddTodo(userId: string, text: string, dueDate?: string, reminderAt?: string, recurrence?: TodoItemData['recurrence']): Promise<TodoItemData> {
  return apiPost(API_ROUTES.TODO_ADD, { user_id: userId, text, due_date: dueDate, reminder_at: reminderAt, recurrence })
}

export function apiToggleTodo(userId: string, todoId: string): Promise<TodoItemData> {
  return apiPost(API_ROUTES.TODO_TOGGLE, { user_id: userId, todo_id: todoId })
}

export function apiEditTodo(userId: string, todoId: string, text?: string, dueDate?: string, reminderAt?: string, recurrence?: TodoItemData['recurrence']): Promise<TodoItemData> {
  return apiPost(API_ROUTES.TODO_EDIT, { user_id: userId, todo_id: todoId, text, due_date: dueDate, reminder_at: reminderAt, recurrence })
}

export function apiDeleteTodo(userId: string, todoId: string): Promise<{ deleted: boolean }> {
  return apiPost(API_ROUTES.TODO_DELETE, { user_id: userId, todo_id: todoId })
}
