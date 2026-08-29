/** Four-library unified-search HTTP request construction tests. */

import { afterEach, describe, expect, it, vi } from 'vitest'

import { searchAllLibraries } from '@/api/unifiedSearch'

describe('unified search API client', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('forwards only selected libraries and exact fulltext/semantic flags', async () => {
    const payload = {
      query: '向量数据库',
      selected_sources: ['library', 'literature'],
      fulltext: false,
      semantic: true,
      results: [],
      groups: { files: [], library: [], components: [], literature: [] },
      counts: { files: 0, library: 0, components: 0, literature: 0 },
      total: 0,
    }
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify(payload), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }))
    vi.stubGlobal('fetch', fetchMock)

    await searchAllLibraries('user/1', '向量数据库', ['library', 'literature'], false, true)

    expect(fetchMock).toHaveBeenCalledWith(
      '/search?user_id=user%2F1&query=%E5%90%91%E9%87%8F%E6%95%B0%E6%8D%AE%E5%BA%93&sources=library%2Cliterature&fulltext=false&semantic=true',
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
  })
})
