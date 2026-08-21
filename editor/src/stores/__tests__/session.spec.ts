/*
 * Agent session store loading tests.
 *
 * Usage:
 * Verifies that shared page components reuse one session-list request while
 * explicit data-changing workflows can still force a backend refresh.
 */
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { createSession, listSessions } from '@/api/session'
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

  it('applies a remote session selection without broadcasting an IPC echo', () => {
    const windowSync = vi.fn()
    Object.defineProperty(window, 'agentEditorDesktop', {
      configurable: true,
      value: { windowSync } as Partial<AgentEditorDesktopApi>,
    })
    const store = useSessionStore()

    store.select('floating-session', false)

    expect(store.currentSessionId).toBe('floating-session')
    expect(windowSync).not.toHaveBeenCalled()
  })

  it('does not let an older session-list response erase a newly created conversation', async () => {
    let finishList: ((value: []) => void) | undefined
    vi.mocked(listSessions).mockReturnValueOnce(new Promise((resolve) => { finishList = resolve }))
    vi.mocked(createSession).mockResolvedValueOnce({
      session_id: 'fresh-session',
      user_id: '1',
      session_name: 'fresh',
      created_at: '2026-08-22T00:00:00Z',
      updated_at: '2026-08-22T00:00:00Z',
    })
    const store = useSessionStore()

    const loading = store.load('1')
    await store.create('1')
    finishList?.([])
    await loading

    expect(store.currentSessionId).toBe('fresh-session')
    expect(store.sessions.map((session) => session.session_id)).toEqual(['fresh-session'])
  })
})
