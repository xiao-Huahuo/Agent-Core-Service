/** Privacy API request construction tests. */

import { afterEach, describe, expect, it, vi } from 'vitest'

import { addPrivacy, deletePrivacy, listPrivacy } from '@/api/privacy'

describe('Privacy API client', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('constructs scoped list, create, and delete requests', async () => {
    const fetchMock = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(new Response(JSON.stringify({ privacy: [] }), { status: 200, headers: { 'content-type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ privacy_id: 'p1' }), { status: 200, headers: { 'content-type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ok: true, deleted: true }), { status: 200, headers: { 'content-type': 'application/json' } }))
    vi.stubGlobal('fetch', fetchMock)

    const payload = { user_id: 'user/1', library_id: 'lib 1', target_type: 'knowledge_path' as const, target_id: 'private/a.png' }
    await listPrivacy({ userId: 'user/1', targetType: 'knowledge_path', libraryId: 'lib 1' })
    await addPrivacy(payload)
    await deletePrivacy(payload)

    expect(fetchMock.mock.calls[0]?.[0]).toBe('/privacy?user_id=user%2F1&target_type=knowledge_path&library_id=lib+1')
    expect(fetchMock.mock.calls[1]?.[0]).toBe('/privacy')
    expect(JSON.parse(String(fetchMock.mock.calls[1]?.[1]?.body))).toEqual(payload)
    expect(fetchMock.mock.calls[2]?.[0]).toBe('/privacy?user_id=user%2F1&library_id=lib+1&target_type=knowledge_path&target_id=private%2Fa.png')
    expect(fetchMock.mock.calls[2]?.[1]?.method).toBe('DELETE')
  })
})
