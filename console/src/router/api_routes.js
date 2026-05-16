/*
 * API 路由常量与拦截器注册。
 *
 * 功能说明:
 * 集中登记所有后端 API 端点路径,便于统一管理与引用。
 * 所有 API 请求的路径常量必须在此处定义,禁止在组件中硬编码 URL。
 *
 * 使用说明:
 * import { API } from '@/router/api_routes'
 * fetch(API.SESSIONS, ...)
 */

/** 后端 API 端点路径常量 */
export const API = {
  /** Agent SSE 流式对话 */
  AGENT_STREAM: '/agent/stream',

  /** Agent LLM 连通性测试 */
  AGENT_TEST: '/agent/test',

  /** Agent trace 事件查询 */
  AGENT_EVENTS: '/agent/events',

  /** Agent 真实召回快照查询 */
  AGENT_RECALL_DETAILS: '/agent/recall-details',

  /** 会话列表 / 创建 */
  SESSIONS: '/sessions',

  /** 会话消息历史 */
  SESSION_MESSAGES: (sessionId) => `/sessions/${sessionId}/messages`,
}
