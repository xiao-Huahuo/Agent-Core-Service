/** Model-management API request construction tests. */

import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  downloadManagedModel,
  fetchModelManagement,
  loadManagedModel,
} from '@/api/settings'

describe('model management API client', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('loads backend-owned model details with the user id', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async () => new Response(JSON.stringify({ models: [] }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }))
    vi.stubGlobal('fetch', fetchMock)

    await fetchModelManagement('user/1')

    expect(fetchMock.mock.calls[0]?.[0]).toBe('/settings/models/management?user_id=user%2F1')
  })

  it('connects model download and load actions to formal endpoints', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async () => new Response('{}', {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }))
    vi.stubGlobal('fetch', fetchMock)

    await downloadManagedModel('embedding')
    await loadManagedModel('rerank')

    expect(fetchMock.mock.calls.map((call) => call[0])).toEqual([
      '/settings/models/download',
      '/settings/models/load',
    ])
    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual({ model: 'embedding' })
    expect(JSON.parse(String(fetchMock.mock.calls[1]?.[1]?.body))).toEqual({ model: 'rerank' })
  })
})
