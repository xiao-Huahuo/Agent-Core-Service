/*
 * Shared Agent change diff tests.
 *
 * Usage:
 * Verifies complete file versions use one real line number per diff row.
 */
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import ChangeDiff from '../ChangeDiff.vue'

describe('ChangeDiff', () => {
  it('shows real line numbers once for complete file versions', () => {
    const wrapper = mount(ChangeDiff, { props: { before: 'one\ntwo\nold', after: 'one\ntwo\nnew' } })

    expect(wrapper.find('.removed .line-number').text()).toBe('3')
    expect(wrapper.find('.added .line-number').text()).toBe('3')
    expect(wrapper.find('.removed .line-text').text()).toBe('old')
    expect(wrapper.find('.added .line-text').text()).toBe('new')
  })

  it('omits line numbers for incomplete live previews', () => {
    const wrapper = mount(ChangeDiff, { props: { before: 'old', after: 'new', showLineNumbers: false } })

    expect(wrapper.find('.line-number').exists()).toBe(false)
  })
})
