/*
 * Chat store reference persistence tests.
 *
 * Verifies that references saved in message metadata survive history reloads.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { createPinia, setActivePinia } from 'pinia'

import { useChatStore } from '../chat'

const apiMocks = vi.hoisted(() => ({
  fetchMessages: vi.fn(),
  streamPrompt: vi.fn(),
  fetchTaskSuggestions: vi.fn(),
  fetchChildAgents: vi.fn(),
  deleteAgentAttachment: vi.fn(),
  listSessions: vi.fn(),
  createSession: vi.fn(),
  deleteSession: vi.fn(),
  updateSessionName: vi.fn(),
  clearAllSessions: vi.fn(),
}))

vi.mock('@/api/session', () => ({
  fetchMessages: apiMocks.fetchMessages,
  listSessions: apiMocks.listSessions,
  createSession: apiMocks.createSession,
  deleteSession: apiMocks.deleteSession,
  updateSessionName: apiMocks.updateSessionName,
  clearAllSessions: apiMocks.clearAllSessions,
}))
vi.mock('@/api/agent', () => ({
  streamPrompt: apiMocks.streamPrompt,
  fetchTaskSuggestions: apiMocks.fetchTaskSuggestions,
  fetchChildAgents: apiMocks.fetchChildAgents,
  deleteAgentAttachment: apiMocks.deleteAgentAttachment,
}))

describe('chat reference history', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    apiMocks.listSessions.mockResolvedValue([])
  })

  it('restores a persisted user reference from message metadata', async () => {
    apiMocks.fetchMessages.mockResolvedValue([
      {
        message_id: 'message-1',
        role: 'user',
        content: '请解释这段话',
        metadata: { reference: '被引用的文档内容' },
        created_at: '2026-07-10T00:00:00Z',
      },
    ])
    const store = useChatStore()

    await store.loadHistory('session-1', 'user-1')

    expect(store.messages).toHaveLength(1)
    expect(store.messages[0]?.reference).toBe('被引用的文档内容')
  })

  it('restores persisted child agent event messages with empty content', async () => {
    const childAgentEvent = {
      event_name: 'child_agent.completed',
      child: {
        run_id: 'child_run_1',
        goal: '整理资料',
        mode: 'background',
        status: 'completed',
        access_mode: 'readonly',
        allowed_tools: ['read_knowledge_file'],
        summary: '完成',
      },
    }
    apiMocks.fetchMessages.mockResolvedValue([
      {
        message_id: 'message-child-agent',
        role: 'assistant',
        content: '',
        metadata: { node: 'child_agent', child_agent_event: childAgentEvent },
        created_at: '2026-08-01T00:00:00Z',
      },
    ])
    const store = useChatStore()

    await store.loadHistory('session-1', 'user-1')

    expect(store.messages).toHaveLength(1)
    expect(store.messages[0]?.node).toBe('child_agent')
    expect(store.messages[0]?.metadata?.child_agent_event).toEqual(childAgentEvent)
  })

  it('records thinking seconds from user bubble append to first final assistant content', async () => {
    const nowSpy = vi.spyOn(performance, 'now')
    nowSpy.mockReturnValueOnce(1000).mockReturnValueOnce(2234)
    apiMocks.streamPrompt.mockImplementation(async function* () {
      yield {
        type: 'delta',
        node: 'agent',
        content: '你好',
        metadata: {
          latency: {
            first_agent_delta_ms: 1234,
          },
        },
      }
    })
    const store = useChatStore()

    await store.send('user-1', 'session-1', '你好')

    const assistant = store.messages.find((message) => message.role === 'assistant')
    expect(assistant?.thinking_seconds).toBe(1.2)
    expect(assistant?.metadata?.backend_first_delta_seconds).toBe(1.2)
    nowSpy.mockRestore()
  })

})
