/*
 * Session API 接口封装。
 *
 * 功能说明:
 * 封装会话管理相关的后端接口调用,包括列出、创建和获取消息历史。
 *
 * 使用说明:
 * import { listSessions, createSession, fetchMessages } from '@/api/session'
 */

import { apiGet, apiPost } from './client'

/**
 * 列出用户的所有会话,按更新时间倒序排列。
 *
 * @param {string} userId 用户 ID
 * @returns {Promise<Array<{session_id: string, user_id: string, session_name: string, created_at: string, updated_at: string}>>}
 */
export function listSessions(userId) {
  return apiGet('/sessions', { user_id: userId })
}

/**
 * 创建新会话。
 *
 * @param {string} userId 用户 ID
 * @param {string} [sessionName] 可选会话名称
 * @returns {Promise<{session_id: string, user_id: string, session_name: string, created_at: string, updated_at: string}>}
 */
export function createSession(userId, sessionName) {
  return apiPost('/sessions', { user_id: userId, session_name: sessionName || undefined })
}

/**
 * 获取会话的消息历史(未摘要消息,按时间正序)。
 *
 * @param {string} sessionId 会话 ID
 * @param {string} userId 用户 ID
 * @param {number} [limit=50] 返回消息数量上限
 * @returns {Promise<Array<{message_id: string, role: string, content: string, tool_calls: Array, metadata: Record<string,any>, created_at: string}>>}
 */
export function fetchMessages(sessionId, userId, limit = 50) {
  return apiGet(`/sessions/${sessionId}/messages`, { user_id: userId, limit })
}
