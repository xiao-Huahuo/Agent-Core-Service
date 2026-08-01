/*
 * Markdown source-link regression tests.
 *
 * Verifies that local document names in assistant answers remain clickable even
 * when the final message does not carry a local citation_map entry.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'

import MarkdownContent from '../MarkdownContent.vue'
import { useWorkspaceStore } from '@/stores/workspace'

describe('MarkdownContent source links', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('links a unique workspace filename even without citation metadata', async () => {
    const workspaceStore = useWorkspaceStore()
    workspaceStore.tree = [
      {
        name: '01_climate_change_nasa.md',
        path: '1/3/01_climate_change_nasa.md',
        isDir: false,
      },
    ]
    const onNavigateSource = vi.fn()

    const wrapper = mount(MarkdownContent, {
      props: {
        content: '气候变化资料主要来自 01_climate_change_nasa.md。',
        citationMap: {},
        onNavigateSource,
      },
    })
    await new Promise((resolve) => window.setTimeout(resolve, 0))

    const sourceLink = wrapper.get('.source-file-link')
    expect(sourceLink.text()).toBe('01_climate_change_nasa.md')
    await sourceLink.trigger('click')
    expect(onNavigateSource).toHaveBeenCalledWith('1/3/01_climate_change_nasa.md')
  })

  it('links filenames after the workspace tree loads later', async () => {
    const workspaceStore = useWorkspaceStore()
    workspaceStore.tree = []
    const onNavigateSource = vi.fn()

    const wrapper = mount(MarkdownContent, {
      props: {
        content: '海洋酸化资料主要来自 09_ocean_acidification_noaa 2.md。',
        citationMap: {},
        onNavigateSource,
      },
    })
    await new Promise((resolve) => window.setTimeout(resolve, 0))
    expect(wrapper.find('.source-file-link').exists()).toBe(false)

    workspaceStore.tree = [
      {
        name: '09_ocean_acidification_noaa 2.md',
        path: '1/3/special/09_ocean_acidification_noaa 2.md',
        isDir: false,
      },
    ]
    await nextTick()
    await new Promise((resolve) => window.setTimeout(resolve, 0))

    const sourceLink = wrapper.get('.source-file-link')
    expect(sourceLink.text()).toBe('09_ocean_acidification_noaa 2.md')
    await sourceLink.trigger('click')
    expect(onNavigateSource).toHaveBeenCalledWith('1/3/special/09_ocean_acidification_noaa 2.md')
  })
})

describe('MarkdownContent streaming code highlight', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('highlights code blocks while still streaming (does not wait for finish)', async () => {
    const wrapper = mount(MarkdownContent, {
      props: {
        content: '```python\nprint("hi")\n```',
        isStreaming: true,
        citationMap: {},
      },
    })
    await nextTick()
    const code = wrapper.find('.markdown-body pre code')
    expect(code.exists()).toBe(true)
    expect(code.classes()).toContain('hljs')
    expect(code.element.innerHTML).toContain('<span')
  })

  it('falls back to plain text for unknown languages without dropping tags', async () => {
    const wrapper = mount(MarkdownContent, {
      props: {
        content: '```not-a-real-lang\n<b>x</b>\n```',
        citationMap: {},
      },
    })
    await nextTick()
    const code = wrapper.find('.markdown-body pre code')
    expect(code.exists()).toBe(true)
    expect(code.element.textContent).toContain('<b>x</b>')
    expect(code.element.innerHTML).not.toContain('<span')
  })
})
