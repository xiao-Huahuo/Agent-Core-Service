/**
 * Top-bar search interaction tests.
 *
 * Usage:
 * Verifies that the compact toolbar variant keeps its searchable icon and
 * keyboard submission while the page variant retains its full submit button.
 */

import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import SearchPalette from '@/components/editor_workspace/SearchPalette.vue'
import { useWorkspaceStore } from '@/stores/workspace'

describe('SearchPalette toolbar variant', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
  })

  it('expands the compact search button without submitting', async () => {
    const workspaceStore = useWorkspaceStore()
    const initialView = workspaceStore.mainView
    const wrapper = mount(SearchPalette, {
      global: { stubs: { Teleport: true, Transition: false } },
    })

    await wrapper.get('.toolbar-search-btn').trigger('click')

    expect(wrapper.get('.search-wrapper').classes()).toContain('focused')
    expect(workspaceStore.mainView).toBe(initialView)
  })

  it('expands on focus and submits the existing query with Enter', async () => {
    const workspaceStore = useWorkspaceStore()
    const wrapper = mount(SearchPalette, {
      global: { stubs: { Teleport: true, Transition: false } },
    })

    workspaceStore.searchQuery = 'heatmap'
    await wrapper.get('.search-input').trigger('focus')
    expect(wrapper.get('.search-wrapper').classes()).toContain('focused')
    expect(wrapper.findAll('.toolbar-search-btn')).toHaveLength(1)
    expect(wrapper.find('.search-submit-btn').exists()).toBe(false)
    expect(wrapper.get('.search-input').attributes('placeholder')).toBe('')
    expect(wrapper.get('.search-input').attributes('aria-label')).toBe('搜索文件')

    await wrapper.get('.search-input').trigger('blur', { relatedTarget: document.body })
    expect(wrapper.get('.search-wrapper').classes()).not.toContain('focused')

    await wrapper.get('.search-input').trigger('focus')
    await wrapper.get('.search-input').trigger('keydown.enter')
    expect(workspaceStore.mainView).toBe('search')
    expect(wrapper.get('.search-wrapper').classes()).not.toContain('focused')
  })

  it('keeps the full submit button on the search page variant', () => {
    const wrapper = mount(SearchPalette, {
      props: { variant: 'page' },
      global: { stubs: { Teleport: true, Transition: false } },
    })

    expect(wrapper.find('.toolbar-search-btn').exists()).toBe(false)
    expect(wrapper.findAll('.search-submit-btn')).toHaveLength(1)
    expect(wrapper.get('.search-input').attributes('placeholder')).toBe('搜索文件...')
  })
})
