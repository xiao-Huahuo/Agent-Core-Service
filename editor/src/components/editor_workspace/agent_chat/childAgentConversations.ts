/*
 * 子 Agent 完整对话的独立并发加载缓存。
 *
 * 用途：主会话加载子 Agent 列表时并发预载每个正式子 Session；每个请求只更新
 * 自己的 keyed 状态，因此并行子 Agent 的完成顺序和失败不会互相覆盖。
 */
import { reactive } from 'vue'

import { fetchMessages } from '@/api/session'
import type { ChildAgentRecord } from '@/api/agent'
import { restoreAgentHistoryMessages } from '@/stores/chat'
import type { AgentChatMessage } from '@/stores/chat'

export interface ChildAgentConversationState {
  messages: AgentChatMessage[]
  loading: boolean
  loaded: boolean
  error: string
}

const states = reactive(new Map<string, ChildAgentConversationState>())
const pendingLoads = new Map<string, Promise<void>>()

export function childAgentConversationState(sessionId: string): ChildAgentConversationState {
  const existing = states.get(sessionId)
  if (existing) return existing
  const created = reactive<ChildAgentConversationState>({
    messages: [],
    loading: false,
    loaded: false,
    error: '',
  })
  states.set(sessionId, created)
  return created
}

export function loadChildAgentConversation(
  sessionId: string,
  userId: string,
  force = false,
): Promise<void> {
  if (!sessionId || !userId) return Promise.resolve()
  const state = childAgentConversationState(sessionId)
  if (!force && state.loaded) return Promise.resolve()
  const pending = pendingLoads.get(sessionId)
  if (pending) return pending

  state.loading = true
  const request = fetchMessages(sessionId, userId)
    .then((records) => {
      state.messages = restoreAgentHistoryMessages(records)
      state.loaded = true
      state.error = ''
    })
    .catch((reason: unknown) => {
      state.error = reason instanceof Error ? reason.message : '子 Agent 对话读取失败'
    })
    .finally(() => {
      state.loading = false
      pendingLoads.delete(sessionId)
    })
  pendingLoads.set(sessionId, request)
  return request
}

export async function preloadChildAgentConversations(
  children: ChildAgentRecord[],
  userId: string,
): Promise<void> {
  await Promise.allSettled(children.map((child) => (
    loadChildAgentConversation(child.conversation_session_id, userId, child.status === 'running')
  )))
}

export function resetChildAgentConversationCache(): void {
  states.clear()
  pendingLoads.clear()
}
