/** Font settings API request tests. */

import { afterEach, describe, expect, it, vi } from 'vitest'

import { saveFontConfig } from '@/api/settings'

describe('Font settings API client', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('sends independent UI and editor text font sizes', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({
        user_id: 'u1',
        ui_font_families: [],
        text_font_families: [],
        ui_font_size_percent: 90,
        text_font_size_percent: 125,
        updated_at: '2026-08-20T00:00:00Z',
      }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await saveFontConfig('u1', {
      uiFontSizePercent: 90,
      textFontSizePercent: 125,
    })

    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toMatchObject({
      user_id: 'u1',
      ui_font_size_percent: 90,
      text_font_size_percent: 125,
    })
  })
})
