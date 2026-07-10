/*
 * Settings API 接口封装。
 *
 * 功能说明:
 * 封装用户设置相关的后端接口调用,包括系统提示词条目和自定义长期记忆。
 */

import { apiGet, apiPost, apiDelete } from './client'
import { API } from '@/router/api_routes'

/* ---- 用户设置档案 ---- */

export function ensureUserProfile(userId) {
  return apiPost(API.SETTINGS_PROFILE, { user_id: userId })
}

/* ---- 系统提示词条目 ---- */

export function fetchSystemPrompt(userId) {
  return apiGet(API.SETTINGS_SYSTEM_PROMPT, { user_id: userId })
}

export function addSystemPromptEntry(userId, content) {
  return apiPost(`${API.SETTINGS_SYSTEM_PROMPT}/entries`, { user_id: userId, content })
}

export function deleteSystemPromptEntry(promptId) {
  return apiDelete(`/settings/system-prompt/entries/${promptId}`)
}

/* ---- 自定义长期记忆 ---- */

export function fetchMemories(userId) {
  return apiGet(API.SETTINGS_MEMORIES, { user_id: userId })
}

export function addMemory(userId, content, importance = 0.5) {
  return apiPost(API.SETTINGS_MEMORIES, { user_id: userId, content, importance })
}

export function deleteMemory(memoryId) {
  return apiDelete(`/settings/memories/${memoryId}`)
}
