/** Knowledge-graph rebuild API request tests. */

import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  cancelKnowledgeGraphTask,
  clearKnowledgeGraphDocument,
  deleteKnowledgeGraphNode,
  rebuildKnowledgeGraph,
} from '@/api/knowledge'

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

  it('uses encoded graph-node mutation routes with the current user', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async () => new Response('{"ok":true}', { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await deleteKnowledgeGraphNode('user/1', 'entity/a')
    await clearKnowledgeGraphDocument('user/1', 'document/a')

    expect(fetchMock.mock.calls[0]?.[0]).toContain('/knowledge/graph/nodes/entity%2Fa?user_id=user%2F1')
    expect(fetchMock.mock.calls[0]?.[1]?.method).toBe('DELETE')
    expect(fetchMock.mock.calls[1]?.[0]).toContain('/knowledge/graph/nodes/document%2Fa/clear')
    expect(JSON.parse(String(fetchMock.mock.calls[1]?.[1]?.body))).toEqual({ user_id: 'user/1' })
  })

  it('posts the exact graph task path to the registered cancellation route', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async () => new Response('{"status":"cancelling"}', { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await cancelKnowledgeGraphTask('user/1', 'notes/a.md')

    expect(fetchMock.mock.calls[0]?.[0]).toContain('/knowledge/graph/rebuild/cancel')
    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual({
      user_id: 'user/1',
      path: 'notes/a.md',
    })
  })
})
