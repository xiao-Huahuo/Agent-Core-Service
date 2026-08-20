/** Knowledge-graph rebuild API request tests. */

import { afterEach, describe, expect, it, vi } from 'vitest'

import { rebuildKnowledgeGraph } from '@/api/knowledge'

describe('knowledge graph rebuild API client', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('sends the target path and force-reextract decision', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response('{"status":"started","message":"ok"}', { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await rebuildKnowledgeGraph('user/1', 'notes/a.md', true)

    const [, request] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(JSON.parse(String(request.body))).toEqual({
      user_id: 'user/1',
      path: 'notes/a.md',
      force: true,
    })
  })
})
