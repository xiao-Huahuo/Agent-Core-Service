/* Knowledge ingestion, OCR, and image-understanding API request tests. */
import { afterEach, describe, expect, it, vi } from 'vitest'

import { saveKnowledgeIngestionConfig } from '@/api/settings'

describe('knowledge ingestion settings API', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('persists the explicit image-understanding switch', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response('{}', {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }))
    vi.stubGlobal('fetch', fetchMock)

    await saveKnowledgeIngestionConfig('u1', { visionUnderstandingEnabled: true })

    expect(fetchMock.mock.calls[0]?.[0]).toBe('/settings/profile/ingestion')
    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual({
      user_id: 'u1',
      vision_understanding_enabled: true,
    })
  })
})
