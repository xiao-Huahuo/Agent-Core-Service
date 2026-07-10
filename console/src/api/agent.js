/*
 * Agent API 接口封装。
 *
 * 功能说明:
 * 封装 Agent 流式对话接口,返回 AsyncGenerator 供 chat store 逐块消费。
 *
 * 使用说明:
 * import { streamPrompt } from '@/api/agent'
 * for await (const chunk of streamPrompt(userId, sessionId, prompt)) { ... }
 */

import { apiGet, streamLines } from './client'
import { API } from '@/router/api_routes'

/**
 * 发起 SSE 流式 Agent 对话请求。
 *
 * @param {string} userId 用户 ID
 * @param {string} sessionId 会话 ID
 * @param {string} prompt 用户输入
 * @returns {AsyncGenerator<{node: string, content: string, tool_calls: Array, trace: Array}>}
 */
export function streamPrompt(userId, sessionId, prompt, options = {}) {
  const params = new URLSearchParams({
    user_id: userId,
    session_id: sessionId,
    prompt,
  })
  return streamLines(`${API.AGENT_STREAM}?${params}`, options)
}

/**
 * 获取指定会话最近一次真实召回快照。
 *
 * @param {string} sessionId 会话 ID
 * @param {string} userId 用户 ID
 * @returns {Promise<{session_id:string,user_id:string,created_at:string,query:string,rag_metrics:Object,memory_recall:Object,knowledge_recall:Object}>}
 */
export function fetchRecallDetails(sessionId, userId, options = {}) {
  return apiGet(API.AGENT_RECALL_DETAILS, { session_id: sessionId, user_id: userId }, options)
}
