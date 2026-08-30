/*
 * 子 Agent 对话并发加载状态回归测试。
 *
 * 用途：验证不同子 Session 的请求并行且错误互不覆盖。
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  childAgentConversationState,
  preloadChildAgentConversations,
  resetChildAgentConversationCache,
} from '../childAgentConversations'
import type { ChildAgentRecord } from '@/api/agent'

const mocks = vi.hoisted(() => ({ fetchMessages: vi.fn() }))

vi.mock('@/api/session', () => ({ fetchMessages: mocks.fetchMessages }))

describe('childAgentConversations', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    resetChildAgentConversationCache()
  })

  it('loads parallel child histories independently', async () => {
    let resolveFirst: ((value: unknown[]) => void) | undefined
    mocks.fetchMessages
      .mockReturnValueOnce(new Promise((resolve) => { resolveFirst = resolve }))
      .mockRejectedValueOnce(new Error('second failed'))

    const loading = preloadChildAgentConversations([
      { conversation_session_id: 'child-a', run_id: 'a', status: 'completed' },
      { conversation_session_id: 'child-b', run_id: 'b', status: 'completed' },
    ] as ChildAgentRecord[], 'u1')
    await Promise.resolve()

    expect(mocks.fetchMessages).toHaveBeenCalledTimes(2)
    expect(childAgentConversationState('child-a').loading).toBe(true)
    resolveFirst?.([{
      message_id: 'm1', session_id: 'child-a', role: 'assistant', content: 'A 完成',
      created_at: '2026-08-30T00:00:00Z', metadata: { node: 'agent' }, tool_calls: [],
    }])
    await loading

    expect(childAgentConversationState('child-a').messages[0]?.content).toBe('A 完成')
    expect(childAgentConversationState('child-a').error).toBe('')
    expect(childAgentConversationState('child-b').messages).toEqual([])
    expect(childAgentConversationState('child-b').error).toBe('second failed')
  })
})
