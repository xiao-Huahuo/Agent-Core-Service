/*
 * Agent session store loading tests.
 *
 * Usage:
 * Verifies that shared page components reuse one session-list request while
 * explicit data-changing workflows can still force a backend refresh.
 */
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { listSessions } from '@/api/session'
import { useSessionStore } from '@/stores/session'

vi.mock('@/api/session', () => ({
  clearAllSessions: vi.fn(),
  createSession: vi.fn(),
  deleteSession: vi.fn(),
  listSessions: vi.fn().mockResolvedValue([]),
  pruneEmptySessions: vi.fn(),
  updateSessionName: vi.fn(),
}))

describe('session store loading', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('coalesces concurrent loads and caches an empty result for the same user', async () => {
    const store = useSessionStore()

    await Promise.all([store.load('1'), store.load('1'), store.load('1')])
    await store.load('1')

    expect(listSessions).toHaveBeenCalledTimes(1)
    expect(store.sessions).toEqual([])
  })

  it('allows an explicit refresh after backend session data changes', async () => {
    const store = useSessionStore()

    await store.load('1')
    await store.load('1', true)

    expect(listSessions).toHaveBeenCalledTimes(2)
  })
})
