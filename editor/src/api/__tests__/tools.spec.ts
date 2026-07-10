/*
 * Agent tool registry API tests.
 *
 * Verifies that the dashboard tool registry client reads from the central
 * Agent tools endpoint.
 */
import { afterEach, describe, expect, it, vi } from 'vitest'

import { fetchAgentTools } from '../tools'

describe('fetchAgentTools', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('requests the registered Agent tools endpoint', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ tool_count: 1, tools: [] }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const payload = await fetchAgentTools()

    expect(payload.tool_count).toBe(1)
    expect(fetchMock).toHaveBeenCalledOnce()
    const [url] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('/agent/tools')
  })

  it('falls back to the backend origin when the frontend server returns html', async () => {
    const fetchMock = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(
        new Response('<!DOCTYPE html><html></html>', {
          status: 200,
          headers: { 'Content-Type': 'text/html' },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ tool_count: 2, tools: [] }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
    vi.stubGlobal('fetch', fetchMock)

    const payload = await fetchAgentTools()

    expect(payload.tool_count).toBe(2)
    expect(fetchMock).toHaveBeenCalledTimes(2)
    const [fallbackUrl, fallbackInit] = fetchMock.mock.calls[1] as [string, RequestInit | undefined]
    expect(fallbackUrl).toBe('http://127.0.0.1:8002/agent/tools')
    expect(fallbackInit).toBeUndefined()
  })
})
