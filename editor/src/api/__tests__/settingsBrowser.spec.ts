/** Embedded-browser settings API request tests. */

import { afterEach, describe, expect, it, vi } from 'vitest'

import { saveWebSearchConfig } from '@/api/settings'

describe('Embedded browser settings API client', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('sends browser proxy and home page through the persisted settings endpoint', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({
        user_id: 'u1',
        proxy_url: '',
        browser_proxy_url: 'socks5://127.0.0.1:1080',
        browser_home_url: 'https://example.com',
        web_search_enabled: false,
        web_search_max_results: 10,
      }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await saveWebSearchConfig('u1', {
      browserProxyUrl: 'socks5://127.0.0.1:1080',
      browserHomeUrl: 'https://example.com',
    })

    expect(fetchMock.mock.calls[0]?.[0]).toBe('/settings/web-search/config')
    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toMatchObject({
      user_id: 'u1',
      browser_proxy_url: 'socks5://127.0.0.1:1080',
      browser_home_url: 'https://example.com',
    })
  })
})
