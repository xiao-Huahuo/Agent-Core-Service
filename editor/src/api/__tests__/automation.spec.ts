/** Automation API request construction tests. */

import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  apiAddAutomation,
  apiDeleteAutomation,
  apiListAutomationRuns,
  apiListAutomations,
  apiToggleAutomation,
} from '@/api/automation'

describe('automation API client', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('encodes user and automation identifiers in list queries', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async () => new Response('[]', { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await apiListAutomations('user/1')
    await apiListAutomationRuns('user/1', 'automation/a', 5)

    expect(fetchMock.mock.calls[0]?.[0]).toBe('/automation/list?user_id=user%2F1')
    expect(fetchMock.mock.calls[1]?.[0]).toBe('/automation/runs?user_id=user%2F1&automation_id=automation%2Fa&limit=5')
  })

  it('creates a timezone-aware recurring task with its access mode', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async () => new Response('{}', { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await apiAddAutomation(
      'u1',
      '日报',
      '整理日报',
      '2026-08-15T09:00:00.000Z',
      'Asia/Shanghai',
      { frequency: 'daily', interval: 1 },
      'sandbox',
    )

    const [, request] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(JSON.parse(String(request.body))).toMatchObject({
      user_id: 'u1',
      next_run_at: '2026-08-15T09:00:00.000Z',
      timezone: 'Asia/Shanghai',
      recurrence: { frequency: 'daily', interval: 1 },
      access_mode: 'sandbox',
    })
  })

  it('sends strict enablement and canonical deletion identifiers', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async () => new Response('{}', { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await apiToggleAutomation('u1', 'automation_1', false)
    await apiDeleteAutomation('u1', 'automation_1')

    expect(JSON.parse(String((fetchMock.mock.calls[0]?.[1] as RequestInit).body))).toEqual({
      user_id: 'u1', automation_id: 'automation_1', enabled: false,
    })
    expect(JSON.parse(String((fetchMock.mock.calls[1]?.[1] as RequestInit).body))).toEqual({
      user_id: 'u1', automation_id: 'automation_1',
    })
  })

  it('propagates server errors so the task row can remain visible', async () => {
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockResolvedValue(new Response(
      JSON.stringify({ detail: 'database busy' }),
      { status: 503, headers: { 'content-type': 'application/json' } },
    )))

    await expect(apiDeleteAutomation('u1', 'automation_1')).rejects.toThrow('database busy')
  })
})
