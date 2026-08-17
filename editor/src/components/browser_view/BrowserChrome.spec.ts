/*
 * Embedded browser chrome regression tests.
 *
 * Usage:
 * Verifies that navigation controls resolve to real local SVG artwork instead
 * of silently rendering an empty IcIcon wrapper.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'

import BrowserChrome from './BrowserChrome.vue'

class ResizeObserverStub {
  observe = vi.fn()
  disconnect = vi.fn()
}

describe('BrowserChrome', () => {
  beforeEach(() => {
    vi.stubGlobal('ResizeObserver', ResizeObserverStub)
  })

  it('renders visible back and forward SVG paths', () => {
    const wrapper = mount(BrowserChrome, {
      props: {
        address: 'https://example.com',
        desktopAvailable: true,
        proxyActive: false,
        state: {
          url: 'https://example.com',
          title: 'Example',
          canGoBack: true,
          canGoForward: true,
          loading: false,
        },
        'onUpdate:address': () => {},
      },
    })
    const buttons = wrapper.findAll('.browser-toolbar > button')

    expect(buttons[0]?.get('svg').html()).toContain('<path')
    expect(buttons[1]?.get('svg').html()).toContain('<path')
  })
})
