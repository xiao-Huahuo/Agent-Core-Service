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

import { streamLines } from './client'

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
  return streamLines(`/agent/stream?${params}`, options)
}
