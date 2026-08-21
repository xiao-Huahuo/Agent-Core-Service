/*
 * Debug API client tests.
 *
 * Usage:
 * Verifies that debug-only API helpers recover from dev-server HTML fallbacks
 * and parse the backend-origin JSON response.
 */

import { afterEach, describe, expect, it, vi } from 'vitest'

import { fetchGlobalConstants, fetchMultimodalIngestionObservation } from '@/api/debug'

describe('Debug API client', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('falls back to backend origin when same-origin debug request returns HTML', async () => {
    const payload = {
      path: 'note.png',
      name: 'note.png',
      source_size: 12,
      chunk_size: 512,
      chunk_overlap: 128,
      json_result: {},
      semantic_chunks: [],
      overlap_chunks: [],
      stats: {
        section_count: 0,
        overlap_chunk_count: 0,
        ocr_enabled: false,
      },
    }
    const fetchMock = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(
        new Response('<!doctype html><title>MetaWeave</title>', {
          status: 200,
          headers: { 'Content-Type': 'text/html' },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(payload), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
    vi.stubGlobal('fetch', fetchMock)

    await expect(fetchMultimodalIngestionObservation('user-1', 'note.png')).resolves.toEqual(payload)

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain('http://127.0.0.1:8002/debug/multimodal-ingestion')
  })

  it('loads the dynamic AgentConfig snapshot through the registered debug route', async () => {
    const payload = {
      config_count: 1,
      constant_count: 1,
      configs: [
        {
          key: 'server',
          name: 'ServerConfig',
          description: '服务配置。',
          constants: [
            {
              name: 'http_port',
              description: 'HTTP 端口。',
              type: 'int',
              value: 8002,
            },
          ],
        },
      ],
    }
    const fetchMock = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(
        new Response('<!doctype html><title>MetaWeave</title>', {
          status: 200,
          headers: { 'Content-Type': 'text/html' },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(payload), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
    vi.stubGlobal('fetch', fetchMock)

    await expect(fetchGlobalConstants()).resolves.toEqual(payload)

    expect(String(fetchMock.mock.calls[0]?.[0])).toBe('/debug/global-constants')
    expect(String(fetchMock.mock.calls[1]?.[0])).toBe('http://127.0.0.1:8002/debug/global-constants')
  })
})
