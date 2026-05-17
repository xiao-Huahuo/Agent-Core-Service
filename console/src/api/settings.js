/*
 * Settings API 接口封装。
 *
 * 功能说明:
 * 封装用户设置相关的后端接口调用,包括系统提示词条目和自定义长期记忆。
 */

import { apiGet, apiPost, apiDelete } from './client'

/* ---- 系统提示词条目 ---- */

export function fetchSystemPrompt(userId) {
  return apiGet('/settings/system-prompt', { user_id: userId })
}

export function addSystemPromptEntry(userId, content) {
  return apiPost('/settings/system-prompt/entries', { user_id: userId, content })
}

export function deleteSystemPromptEntry(promptId) {
  return apiDelete(`/settings/system-prompt/entries/${promptId}`)
}

/* ---- 自定义长期记忆 ---- */

export function fetchMemories(userId) {
  return apiGet('/settings/memories', { user_id: userId })
}

export function addMemory(userId, content, importance = 0.5) {
  return apiPost('/settings/memories', { user_id: userId, content, importance })
}

export function deleteMemory(memoryId) {
  return apiDelete(`/settings/memories/${memoryId}`)
}
