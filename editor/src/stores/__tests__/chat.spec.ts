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
}))

vi.mock('@/api/session', () => ({ fetchMessages: apiMocks.fetchMessages }))
vi.mock('@/api/agent', () => ({ streamPrompt: apiMocks.streamPrompt }))

describe('chat reference history', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
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
})
