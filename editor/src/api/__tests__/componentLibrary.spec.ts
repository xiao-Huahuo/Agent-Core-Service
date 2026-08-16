/** Component library API request construction tests. */

import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  createComponentLibraryItem,
  listComponentLibraryItems,
  renameComponentLibraryItem,
} from '@/api/componentLibrary'

describe('Component library API client', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('lists one fixed tag through the shared API client', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ components: [], tags: [] }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await listComponentLibraryItems('user/1', 'toggle switches')

    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      '/component-library/components?user_id=user%2F1&tag=toggle+switches',
    )
  })

  it('uploads source, one tag, and the selected file name as JSON', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ component: {} }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await createComponentLibraryItem({
      user_id: 'u1',
      source: '<template><button>OK</button></template>',
      tag: 'buttons',
      filename: 'button.vue',
    })

    expect(fetchMock.mock.calls[0]?.[0]).toBe('/component-library/components')
    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual({
      user_id: 'u1',
      source: '<template><button>OK</button></template>',
      tag: 'buttons',
      filename: 'button.vue',
    })
  })

  it('renames one persisted component through the shared endpoint', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ component: {} }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await renameComponentLibraryItem('u1', 'cards/old.vue', '新卡片')

    expect(fetchMock.mock.calls[0]?.[0]).toBe('/component-library/components')
    expect(fetchMock.mock.calls[0]?.[1]?.method).toBe('PATCH')
    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual({
      user_id: 'u1',
      component_id: 'cards/old.vue',
      title: '新卡片',
    })
  })
})
