/*
 * Debug API client tests.
 *
 * Usage:
 * Verifies that debug-only API helpers recover from dev-server HTML fallbacks
 * and parse the backend-origin JSON response.
 */

import { afterEach, describe, expect, it, vi } from 'vitest'

import { fetchMultimodalIngestionObservation } from '@/api/debug'

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
})
