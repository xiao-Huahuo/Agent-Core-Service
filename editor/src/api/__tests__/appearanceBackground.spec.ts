/** Appearance background API request tests. */

import { afterEach, describe, expect, it, vi } from 'vitest'

import { saveAppearanceConfig } from '@/api/settings'

describe('appearance background API client', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('persists and resets the uploaded cover URL through appearance config', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async () => new Response(JSON.stringify({
      user_id: 'u1', theme_primary_color: '', theme_soft_color: '', show_backlinks: false,
      background_cover_url: '/library/assets/u1/cover.png', updated_at: '',
    }), { status: 200, headers: { 'content-type': 'application/json' } }))
    vi.stubGlobal('fetch', fetchMock)

    await saveAppearanceConfig('u1', { backgroundCoverUrl: '/library/assets/u1/cover.png' })
    await saveAppearanceConfig('u1', { backgroundCoverUrl: '' })

    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toMatchObject({
      user_id: 'u1', background_cover_url: '/library/assets/u1/cover.png',
    })
    expect(JSON.parse(String(fetchMock.mock.calls[1]?.[1]?.body))).toMatchObject({
      user_id: 'u1', background_cover_url: '',
    })
  })
})
