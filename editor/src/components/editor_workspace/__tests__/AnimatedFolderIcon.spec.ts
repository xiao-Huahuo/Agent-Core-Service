/**
 * Animated folder artwork tests.
 *
 * Usage:
 * Verifies the two supported resource-manager sizes and the persistent open
 * state used by selected folder tiles.
 */
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import AnimatedFolderIcon from '../AnimatedFolderIcon.vue'

describe('AnimatedFolderIcon', () => {
  it('renders the attached three-paper folder artwork at medium size', () => {
    const wrapper = mount(AnimatedFolderIcon, { props: { size: 'medium' } })

    expect(wrapper.classes()).toContain('is-medium')
    expect(wrapper.findAll('.folder-paper')).toHaveLength(3)
    expect(wrapper.attributes('aria-hidden')).toBe('true')
  })

  it('opens the large folder artwork when its tile is selected', () => {
    const wrapper = mount(AnimatedFolderIcon, { props: { size: 'large', open: true } })

    expect(wrapper.classes()).toEqual(expect.arrayContaining(['is-large', 'is-open']))
  })
})
