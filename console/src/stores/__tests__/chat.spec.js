/*
 * Chat store streaming tests.
 *
 * Usage:
 * Verifies that SSE delta chunks are appended instead of replacing previous
 * assistant content while preserving action-node tool traces.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useChatStore } from '../chat'

const apiMocks = vi.hoisted(() => ({
  streamPrompt: vi.fn(),
  listSessions: vi.fn(),
  createSession: vi.fn(),
  deleteSession: vi.fn(),
  clearAllSessions: vi.fn(),
  updateSessionName: vi.fn(),
}))

vi.mock('@/api/agent', () => ({
  streamPrompt: apiMocks.streamPrompt,
}))

vi.mock('@/api/session', () => ({
  listSessions: apiMocks.listSessions,
  createSession: apiMocks.createSession,
  deleteSession: apiMocks.deleteSession,
  clearAllSessions: apiMocks.clearAllSessions,
  updateSessionName: apiMocks.updateSessionName,
}))

async function* streamChunks(chunks) {
  for (const chunk of chunks) {
    yield chunk
  }
}

describe('chat store streaming', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    apiMocks.listSessions.mockResolvedValue([])
  })

  it('appends delta chunks instead of replacing previous assistant output', async () => {
    apiMocks.streamPrompt.mockReturnValue(streamChunks([
      { type: 'delta', node: 'agent', content: 'Hel', tool_calls: [], trace: [] },
      { type: 'delta', node: 'agent', content: 'lo', tool_calls: [], trace: [] },
    ]))
    const store = useChatStore()

    await store.send('user-1', 'session-1', 'say hello')

    const assistant = store.messages.find((message) => message.role === 'assistant')
    expect(assistant?.content).toBe('Hello')
  })

  it('keeps completed tool traces as action assistant messages', async () => {
    apiMocks.streamPrompt.mockReturnValue(streamChunks([
      {
        node: 'action',
        content: '',
        tool_calls: [],
        trace: [{ event: 'tool_call_end', tool_name: 'web_search', display_name: '搜索', result_count: 3 }],
      },
    ]))
    const store = useChatStore()

    await store.send('user-1', 'session-1', 'search docs')

    const action = store.messages.find((message) => message.role === 'assistant' && message.node === 'action')
    expect(action?.trace).toHaveLength(1)
    expect(action?.trace?.[0]?.tool_name).toBe('web_search')
  })

  it('replaces a final full-content node event after previous delta chunks', async () => {
    apiMocks.streamPrompt.mockReturnValue(streamChunks([
      { type: 'delta', node: 'agent', content: 'Hel', tool_calls: [], trace: [] },
      { type: 'delta', node: 'agent', content: 'lo', tool_calls: [], trace: [] },
      { node: 'agent', content: 'Hello', tool_calls: [], trace: [] },
    ]))
    const store = useChatStore()

    await store.send('user-1', 'session-1', 'say hello')

    const assistant = store.messages.find((message) => message.role === 'assistant')
    expect(assistant?.content).toBe('Hello')
  })
})
