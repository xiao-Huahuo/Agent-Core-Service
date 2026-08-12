/* Agent change API request construction tests. */

import { afterEach, describe, expect, it, vi } from 'vitest'
import { fetchSessionChanges, undoSessionChange } from '@/api/agentChanges'

describe('Agent change API client', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('loads the latest persisted change snapshot for an encoded session id', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify({ change_snapshot: null }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)
    await fetchSessionChanges('session/a')
    expect(fetchMock.mock.calls[0]?.[0]).toBe('/sessions/session%2Fa/changes')
  })

  it('posts only the user id to the guarded undo endpoint', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify({ change_snapshot: {} }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)
    await undoSessionChange('session-1', 'change-1', 'user-1')
    const [path, request] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(path).toBe('/sessions/session-1/changes/change-1/undo')
    expect(JSON.parse(String(request.body))).toEqual({ user_id: 'user-1' })
  })
})
