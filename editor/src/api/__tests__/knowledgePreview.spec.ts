/** Knowledge preview API request and PDF-thumbnail response tests. */

import { afterEach, describe, expect, it, vi } from 'vitest'

import { previewKnowledgeFile } from '@/api/knowledge'

describe('knowledge preview API client', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('returns the backend PDF first-page thumbnail URL', async () => {
    const payload = {
      path: 'papers/demo.pdf',
      kind: 'pdf',
      thumbnail_url: '/knowledge/assets/pdf_preview/key/page-1.png',
      mtime: '2026-08-20T00:00:00',
      size: 128,
      extension: '.pdf',
      readonly: true,
    }
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify(payload), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }))
    vi.stubGlobal('fetch', fetchMock)

    const preview = await previewKnowledgeFile('user/1', 'papers/demo.pdf')

    expect(fetchMock).toHaveBeenCalledWith(
      '/knowledge/files/preview?user_id=user%2F1&path=papers%2Fdemo.pdf',
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
    expect(preview.thumbnail_url).toBe('/knowledge/assets/pdf_preview/key/page-1.png')
  })
})
