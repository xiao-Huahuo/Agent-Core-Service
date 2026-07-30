/*
 * Cross-session Dashboard observability history tests.
 *
 * Verifies range-bounded lazy loading, shared requests, and loading state.
 */
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { SessionRecord } from '@/api/session'
import {
  OBS_HISTORY_RANGE_OPTIONS,
  formatObsHistoryRange,
  useObsHistory,
} from '@/composable/useObsHistory'

const sessions: SessionRecord[] = [
  {
    session_id: 'session-a',
    user_id: 'user-1',
    session_name: '对话 A',
    created_at: '2026-07-30T09:00:00Z',
    updated_at: '2026-07-30T09:00:02Z',
  },
  {
    session_id: 'session-b',
    user_id: 'user-1',
    session_name: '对话 B',
    created_at: '2026-07-30T10:00:00Z',
    updated_at: '2026-07-30T10:00:02Z',
  },
]

function sessionMessages(sessionId: string, hour: string, relevance: number) {
  return [
    {
      message_id: `${sessionId}-user`,
      session_id: sessionId,
      role: 'user',
      content: '问题',
      created_at: `2026-07-30T${hour}:00:00Z`,
    },
    {
      message_id: `${sessionId}-rag`,
      session_id: sessionId,
      role: 'system',
      content: '上下文',
      metadata: {
        rag_metrics: {
          fill_rate: 50,
          avg_relevance: relevance,
          confidence: relevance,
        },
      },
      created_at: `2026-07-30T${hour}:00:01Z`,
    },
    {
      message_id: `${sessionId}-assistant`,
      session_id: sessionId,
      role: 'assistant',
      content: '回答',
      metadata: {
        node: 'agent',
        trace: [{ node: 'agent', event: 'model_response', duration_ms: 1200 }],
      },
      created_at: `2026-07-30T${hour}:00:02Z`,
    },
  ]
}

describe('useObsHistory', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('formats every range with an explicit chart unit', () => {
    expect(formatObsHistoryRange(20, '次', 'RAG')).toBe('最近 20 次 RAG')
    expect(formatObsHistoryRange(20, '条', 'message')).toBe('最近 20 条 message')
    expect(formatObsHistoryRange('all', '次', 'RAG')).toBe('全部 RAG')
    expect(formatObsHistoryRange('all', '条', 'message')).toBe('全部 message')
  })

  it('defaults both charts to 20 turns and shares their identical history request', async () => {
    const records = [
      ...sessionMessages('session-a', '09', 70),
      ...sessionMessages('session-b', '10', 80),
    ]
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(
      () => Promise.resolve(
        new Response(JSON.stringify(records), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    )
    vi.stubGlobal('fetch', fetchMock)
    const history = useObsHistory()

    expect(OBS_HISTORY_RANGE_OPTIONS).toEqual([5, 10, 20, 50, 100, 200, 500, 1000, 'all'])
    expect(history.ragLimit.value).toBe(20)
    expect(history.latencyLimit.value).toBe(20)

    await Promise.all([
      history.loadRag('user-1', sessions),
      history.loadLatency('user-1', sessions),
    ])

    expect(history.ragHistory.value).toHaveLength(2)
    expect(history.latencyTurns.value).toHaveLength(2)
    expect(history.latencyTurns.value.map((turn) => turn.sessionName)).toEqual(['对话 A', '对话 B'])
    expect(fetchMock).toHaveBeenCalledOnce()
    expect(fetchMock.mock.calls[0]?.[0]).toBe('/sessions/observability/history?user_id=user-1&limit=20')
  })

  it('shares one in-flight request between duplicate latency range loads', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(
      () => Promise.resolve(
        new Response(JSON.stringify([]), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    )
    vi.stubGlobal('fetch', fetchMock)
    const history = useObsHistory()

    await Promise.all([
      history.loadLatency('deduplicated-user', [], 50),
      history.loadLatency('deduplicated-user', [], 50),
    ])

    expect(fetchMock).toHaveBeenCalledOnce()
  })

  it('exposes loading state until the selected range request finishes', async () => {
    let resolveFetch: ((response: Response) => void) | undefined
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(
      () => new Promise<Response>((resolve) => {
        resolveFetch = resolve
      }),
    )
    vi.stubGlobal('fetch', fetchMock)
    const history = useObsHistory()

    const request = history.loadLatency('loading-user', [], 5)

    expect(history.latencyLoading.value).toBe(true)
    resolveFetch?.(
      new Response(JSON.stringify([]), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    await request
    expect(history.latencyLoading.value).toBe(false)
  })
})
