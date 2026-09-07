/** Component library API request construction tests. */

import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  createComponentLibraryItem,
  deleteComponentLibraryItem,
  listComponentLibraryItems,
  renameComponentLibraryItem,
  updateComponentLibraryItem,
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

  it('preserves component source beyond one MiB and one million characters', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ component: {} }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)
    const source = `<div>large</div><!--${'x'.repeat(1_100_000)}-->`

    expect(source.length).toBeGreaterThan(1_000_000)
    expect(new TextEncoder().encode(source).byteLength).toBeGreaterThan(1024 * 1024)

    await createComponentLibraryItem({
      user_id: 'u1',
      source,
      tag: 'cards',
      filename: 'large.html',
    })

    const body = JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body)) as { source: string }
    expect(body.source).toBe(source)
  })

  it('uploads drawing-script language and its optional persisted cover reference', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ component: {} }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await createComponentLibraryItem({
      user_id: 'u1',
      source: 'plt.plot([1, 2])',
      tag: 'drawing scripts',
      filename: '曲线图.script',
      script_language: 'Python',
      cover_asset_id: 'asset-plot',
    })

    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual({
      user_id: 'u1',
      source: 'plt.plot([1, 2])',
      tag: 'drawing scripts',
      filename: '曲线图.script',
      script_language: 'Python',
      cover_asset_id: 'asset-plot',
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

  it('updates persisted component source through the same canonical endpoint', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ component: {} }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await updateComponentLibraryItem('u1', 'cards/old.vue', {
      source: '<template><article>new</article></template>',
    })

    expect(fetchMock.mock.calls[0]?.[1]?.method).toBe('PATCH')
    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual({
      user_id: 'u1',
      component_id: 'cards/old.vue',
      source: '<template><article>new</article></template>',
    })
  })

  it('deletes one component through its canonical component-library endpoint', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ component_id: 'cards/old.vue', deleted: true }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await deleteComponentLibraryItem('user/1', 'cards/old.vue')

    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      '/component-library/components?user_id=user%2F1&component_id=cards%2Fold.vue',
    )
    expect(fetchMock.mock.calls[0]?.[1]?.method).toBe('DELETE')
  })
})
