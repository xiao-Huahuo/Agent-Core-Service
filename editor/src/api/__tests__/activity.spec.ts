/** Daily activity heatmap API request construction tests. */

import { afterEach, describe, expect, it, vi } from 'vitest'

import { fetchActivityHeatmap } from '@/api/activity'

describe('Activity heatmap API client', () => {
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('requests the persisted 53-week heatmap for one user and timezone', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ days: [], summaries: {} }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await fetchActivityHeatmap('user/1', 'Asia/Shanghai')

    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      '/activity/heatmap?user_id=user%2F1&days=364&timezone=Asia%2FShanghai',
    )
  })

  it('allows the one-time historical backfill to exceed the shared request timeout', async () => {
    vi.useFakeTimers()
    let requestSignal: AbortSignal | undefined
    const fetchMock = vi.fn<typeof fetch>().mockImplementation((_input, init) => {
      requestSignal = init?.signal ?? undefined
      return new Promise<Response>((_resolve, reject) => {
        requestSignal?.addEventListener('abort', () => reject(requestSignal?.reason), { once: true })
      })
    })
    vi.stubGlobal('fetch', fetchMock)

    const request = fetchActivityHeatmap('user-1').catch(() => undefined)
    await vi.advanceTimersByTimeAsync(30_001)
    expect(requestSignal?.aborted).toBe(false)
    await vi.advanceTimersByTimeAsync(89_999)
    expect(requestSignal?.aborted).toBe(true)
    await request
  })
})
