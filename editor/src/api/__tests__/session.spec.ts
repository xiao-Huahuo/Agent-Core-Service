/*
 * Session observability history API tests.
 *
 * Verifies direct-backend retry and prevention of per-session request fan-out.
 */
import { afterEach, describe, expect, it, vi } from 'vitest'

import { fetchUserMessageHistory } from '../session'

describe('fetchUserMessageHistory', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('retries the complete history route directly when the frontend returns html', async () => {
    const fetchMock = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(
        new Response('<!DOCTYPE html><html></html>', {
          status: 200,
          headers: { 'Content-Type': 'text/html' },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify([
          {
            message_id: 'message-old',
            session_id: 'session-old',
            role: 'user',
            content: '第一次对话',
            created_at: '2026-07-30T09:00:00Z',
          },
          {
            message_id: 'message-new',
            session_id: 'session-new',
            role: 'user',
            content: '第二次对话',
            created_at: '2026-07-30T10:00:00Z',
          },
        ]), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
    vi.stubGlobal('fetch', fetchMock)

    const history = await fetchUserMessageHistory('user-1', 20)

    expect(history.map((message) => message.message_id)).toEqual(['message-old', 'message-new'])
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      '/sessions/observability/history?user_id=user-1&limit=20',
      'http://127.0.0.1:8002/sessions/observability/history?user_id=user-1&limit=20',
    ])
  })

  it('does not fan out across sessions when a bounded history route is unavailable', async () => {
    const fetchMock = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(
        new Response('<!DOCTYPE html><html></html>', {
          status: 200,
          headers: { 'Content-Type': 'text/html' },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: 'Not Found' }), {
          status: 404,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
    vi.stubGlobal('fetch', fetchMock)

    await expect(fetchUserMessageHistory('user-1', 20)).rejects.toThrow('请重启后端服务')

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      '/sessions/observability/history?user_id=user-1&limit=20',
      'http://127.0.0.1:8002/sessions/observability/history?user_id=user-1&limit=20',
    ])
  })
})
