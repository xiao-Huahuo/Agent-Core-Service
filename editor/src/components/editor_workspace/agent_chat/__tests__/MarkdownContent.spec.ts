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
    const onNavigateSource = vi.fn<(uri: string) => void>()

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

  it('renders inline and display math after DOMPurify', async () => {
    const wrapper = mount(MarkdownContent, {
      props: {
        content: '行内 $a^2+b^2$ 与块级\n\n$$\\sum_{i=1}^{n} i$$\n\n结束',
        citationMap: {},
      },
    })
    await new Promise((resolve) => window.setTimeout(resolve, 0))

    expect(wrapper.find('.katex').exists()).toBe(true)
    expect(wrapper.find('.katex-display').exists()).toBe(true)
    // KaTeX 依赖的 style 定位属性经 DOMPurify 后保留(非空 style)
    const styles = wrapper.findAll('.katex [style]')
    expect(styles.length).toBeGreaterThan(0)
  })

  it('does not render math inside code fences', async () => {
    const wrapper = mount(MarkdownContent, {
      props: {
        content: '代码: ```js\nconst price = "$5 and $10";\n```',
        citationMap: {},
      },
    })
    await new Promise((resolve) => window.setTimeout(resolve, 0))

    expect(wrapper.find('.katex').exists()).toBe(false)
    expect(wrapper.text()).toContain('$5 and $10')
  })

  it('links filenames after the workspace tree loads later', async () => {
    const workspaceStore = useWorkspaceStore()
    workspaceStore.tree = []
    const onNavigateSource = vi.fn<(uri: string) => void>()

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

  it('reveals only newly appended prose words and keeps a trailing stream cursor', async () => {
    const wrapper = mount(MarkdownContent, {
      props: {
        content: '第一段文字',
        isStreaming: true,
        citationMap: {},
      },
    })
    await nextTick()

    expect(wrapper.find('.stream-cursor').exists()).toBe(true)
    expect(wrapper.findAll('.stream-reveal-word').map((word) => word.text()).join('')).toBe('第一段文字')

    await wrapper.setProps({ content: '第一段文字 新到 内容' })
    await nextTick()

    const words = wrapper.findAll('.stream-reveal-word')
    expect(words.map((word) => word.text())).toEqual(['新到', '内容'])
    expect(wrapper.text()).toContain('第一段文字 新到 内容')
  })

  it('removes the stream cursor without altering the final markdown content', async () => {
    const wrapper = mount(MarkdownContent, {
      props: {
        content: '**完成内容**',
        isStreaming: true,
        citationMap: {},
      },
    })
    await nextTick()

    await wrapper.setProps({ isStreaming: false })
    await nextTick()

    expect(wrapper.find('.stream-cursor').exists()).toBe(false)
    expect(wrapper.get('strong').text()).toBe('完成内容')
  })
})
