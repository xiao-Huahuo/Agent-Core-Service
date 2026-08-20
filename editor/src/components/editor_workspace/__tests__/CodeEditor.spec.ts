/*
 * Markdown editor context-menu regression tests.
 *
 * Verifies that Markdown-only right-click commands transform the textarea
 * selection instead of depending on the browser's native context menu.
 */
import { describe, expect, it, vi } from 'vitest'

import { flushPromises, mount } from '@vue/test-utils'

import CodeEditor from '../CodeEditor.vue'
import type { KnowledgeFileNode } from '@/types/knowledge'

function mountMarkdownEditor(value: string, wikiFiles: KnowledgeFileNode[] = []) {
  const wrapper = mount(CodeEditor, {
    props: {
      modelValue: value,
      language: 'md',
      wikiFiles,
      'onUpdate:modelValue': (nextValue: string) => wrapper.setProps({ modelValue: nextValue }),
    },
  })
  return wrapper
}

describe('CodeEditor Markdown context menu', () => {
  it('opens and filters file suggestions after typing [[', async () => {
    const wrapper = mountMarkdownEditor('', [
      { name: '深度学习.md', path: '机器学习/深度学习.md', isDir: false },
      { name: 'tmp.md', path: '杂项/tmp.md', isDir: false },
    ])
    const textarea = wrapper.get('textarea')
    const element = textarea.element as HTMLTextAreaElement
    element.value = '[[深度'
    element.setSelectionRange(4, 4)
    await textarea.trigger('input')

    expect(wrapper.find('.wiki-link-suggest').exists()).toBe(true)
    expect(wrapper.findAll('.wiki-link-suggest-item')).toHaveLength(1)
    expect(wrapper.get('.wiki-link-suggest-item').text()).toContain('深度学习')
    expect(wrapper.get('.wiki-link-suggest-item').text()).toContain('机器学习/')
  })

  it('selects a wiki target with Enter and supports embedded prefixes', async () => {
    const files = [{ name: '深度学习.md', path: '机器学习/深度学习.md', isDir: false }]
    const wrapper = mountMarkdownEditor('', files)
    const textarea = wrapper.get('textarea')
    const element = textarea.element as HTMLTextAreaElement
    element.value = '![[深'
    element.setSelectionRange(4, 4)
    await textarea.trigger('input')
    await textarea.trigger('keydown', { key: 'Enter' })

    expect((wrapper.props() as { modelValue: string }).modelValue).toBe('![[机器学习/深度学习]]')
  })

  it('offers wiki and embed insertion in the Markdown context menu', async () => {
    const wrapper = mountMarkdownEditor('')

    await wrapper.get('textarea').trigger('contextmenu', { clientX: 12, clientY: 12 })
    await wrapper.findAll('.markdown-context-parent').find((button) => button.text().includes('插入'))?.trigger('click')

    const labels = wrapper.findAll('.markdown-context-submenu button').map((button) => button.text())
    expect(labels).toContain('插入 Wiki 链接')
    expect(labels).toContain('插入嵌入链接')
    expect(wrapper.find('.markdown-context-action').text()).toContain('显示反向链接')
  })

  it('emits scroll ratio and caret offset for Split synchronization', async () => {
    const wrapper = mountMarkdownEditor('alpha\nbeta\ngamma')
    const textarea = wrapper.get('textarea').element as HTMLTextAreaElement
    Object.defineProperty(textarea, 'scrollHeight', { configurable: true, value: 300 })
    Object.defineProperty(textarea, 'clientHeight', { configurable: true, value: 100 })
    textarea.scrollTop = 100
    textarea.setSelectionRange(6, 6)

    await wrapper.get('textarea').trigger('scroll')

    expect(wrapper.emitted('scroll')?.[0]?.[0]).toEqual({
      ratio: 0.5,
      cursorOffset: 6,
      contentLength: 16,
    })
  })

  it('keeps the highlight content pixel-aligned while the clipping layer stays fixed', async () => {
    const wrapper = mountMarkdownEditor('alpha\nbeta\ngamma')
    const textarea = wrapper.get('textarea').element as HTMLTextAreaElement
    Object.defineProperty(textarea, 'scrollHeight', { configurable: true, value: 300 })
    Object.defineProperty(textarea, 'clientHeight', { configurable: true, value: 100 })
    textarea.scrollTop = 100
    textarea.scrollLeft = 40

    await wrapper.get('textarea').trigger('scroll')

    const layer = wrapper.get('.highlight-layer').element as HTMLElement
    const content = wrapper.get('.highlight-content').element as HTMLElement
    expect(layer.style.transform).toBe('')
    expect(content.style.transform).toBe('translate3d(-40px, -100px, 0)')
  })

  it('renders syntax highlighting directly in the editable source surface', () => {
    const wrapper = mount(CodeEditor, {
      props: {
        modelValue: 'def greet():\n    return "hello"',
        language: 'python',
      },
    })

    expect(wrapper.find('.syntax-highlight-layer').exists()).toBe(true)
    expect(wrapper.find('.syntax-highlight-layer').html()).toContain('<span')
    expect(wrapper.get('textarea').classes()).toContain('syntax-highlighted')
  })

  it('highlights Markdown symbols with preview-like colors', () => {
    const wrapper = mount(CodeEditor, {
      props: {
        modelValue: '# 标题\n\n**加粗**\n\n- 列表\n\n> 引用\n\n`code` [链接](https://example.com)',
        language: 'md',
      },
    })

    const layer = wrapper.find('.syntax-highlight-layer')
    expect(layer.exists()).toBe(true)
    expect(layer.classes()).toContain('markdown-highlight-layer')
    const html = layer.html()
    expect(html).toContain('hljs-section')
    expect(html).toContain('hljs-strong')
    expect(html).toContain('hljs-bullet')
    expect(html).toContain('hljs-quote')
    expect(html).toContain('hljs-code')
    expect(wrapper.get('textarea').classes()).toContain('syntax-highlighted')
  })

  it('renders an external query as yellow highlights while remaining readonly', () => {
    const wrapper = mount(CodeEditor, {
      props: {
        modelValue: 'alpha beta alpha',
        language: 'text',
        readonly: true,
        highlightQuery: 'alpha',
      },
    })

    expect(wrapper.get('textarea').attributes('readonly')).toBeDefined()
    expect(wrapper.findAll('.highlight-layer .match-highlight')).toHaveLength(2)
    expect(wrapper.find('.find-replace-bar').exists()).toBe(false)
  })

  it('blocks paste and save shortcuts while readonly', async () => {
    const readText = vi.fn().mockResolvedValue('changed')
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { readText },
    })
    const wrapper = mount(CodeEditor, {
      props: {
        modelValue: 'original',
        language: 'text',
        readonly: true,
      },
    })
    const textarea = wrapper.get('textarea')

    await textarea.trigger('keydown', { key: 'v', ctrlKey: true, shiftKey: true })
    await textarea.trigger('keydown', { key: 's', ctrlKey: true })
    await flushPromises()

    expect(readText).not.toHaveBeenCalled()
    expect((wrapper.props() as { modelValue: string }).modelValue).toBe('original')
    expect(wrapper.emitted('save')).toBeUndefined()
  })

  it('inserts a Markdown image link when clipboard contains an image', async () => {
    const read = vi.fn().mockResolvedValue([
      {
        types: ['image/png'],
        getType: vi.fn().mockResolvedValue(new Blob(['image'], { type: 'image/png' })),
      },
    ])
    const readText = vi.fn().mockResolvedValue('plain text')
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { read, readText },
    })
    const pasteImage = vi.fn().mockResolvedValue('![](./assets/image.png)')
    const wrapper = mount(CodeEditor, {
      props: {
        modelValue: 'before ',
        language: 'md',
        pasteImage,
        'onUpdate:modelValue': (nextValue: string) => wrapper.setProps({ modelValue: nextValue }),
      },
    })
    const textareaWrapper = wrapper.get('textarea')
    const textarea = textareaWrapper.element as HTMLTextAreaElement
    textarea.setSelectionRange(7, 7)

    await textareaWrapper.trigger('keydown', { key: 'v', ctrlKey: true, shiftKey: true })
    await flushPromises()

    expect(pasteImage).toHaveBeenCalledOnce()
    expect(readText).not.toHaveBeenCalled()
    expect((wrapper.props() as { modelValue: string }).modelValue).toBe('before ![](./assets/image.png)')
  })

  it('handles native paste events for clipboard images', async () => {
    const pasteImage = vi.fn().mockResolvedValue('![](./assets/native.png)')
    const wrapper = mount(CodeEditor, {
      props: {
        modelValue: '',
        language: 'md',
        pasteImage,
        'onUpdate:modelValue': (nextValue: string) => wrapper.setProps({ modelValue: nextValue }),
      },
    })
    const preventDefault = vi.fn()
    const getAsFile = vi.fn().mockReturnValue(new File(['image'], 'clipboard.png', { type: 'image/png' }))
    const pasteEvent = new Event('paste', { bubbles: true, cancelable: true })
    Object.defineProperty(pasteEvent, 'clipboardData', {
      value: { items: [{ type: 'image/png', getAsFile }] },
    })
    pasteEvent.preventDefault = preventDefault

    wrapper.get('textarea').element.dispatchEvent(pasteEvent)
    await flushPromises()

    expect(preventDefault).toHaveBeenCalledOnce()
    expect(pasteImage).toHaveBeenCalledOnce()
    expect((wrapper.props() as { modelValue: string }).modelValue).toBe('![](./assets/native.png)')
  })

  it('wraps the selected text as bold Markdown', async () => {
    const wrapper = mountMarkdownEditor('hello')
    const textarea = wrapper.get('textarea').element as HTMLTextAreaElement
    textarea.setSelectionRange(0, 5)

    await wrapper.get('textarea').trigger('contextmenu', { clientX: 12, clientY: 12 })
    const boldButton = wrapper.findAll('.markdown-context-submenu button').find((button) => button.text().includes('加粗'))
    await boldButton?.trigger('click')

    expect((wrapper.props() as { modelValue: string }).modelValue).toBe('**hello**')
  })

  it('turns the current line into a heading', async () => {
    const wrapper = mountMarkdownEditor('alpha\nbeta')
    const textarea = wrapper.get('textarea').element as HTMLTextAreaElement
    textarea.setSelectionRange(6, 10)

    await wrapper.get('textarea').trigger('contextmenu', { clientX: 12, clientY: 12 })
    await wrapper.findAll('.markdown-context-parent').find((button) => button.text().includes('段落设置'))?.trigger('click')
    const headingButton = wrapper.findAll('.markdown-context-submenu button').find((button) => button.text().includes('2 级标题'))
    await headingButton?.trigger('click')

    expect((wrapper.props() as { modelValue: string }).modelValue).toBe('alpha\n## beta')
  })

  it('inserts a Markdown table row from the context menu', async () => {
    const wrapper = mountMarkdownEditor('| A | B |\n| --- | --- |\n| 1 | 2 |')
    const textarea = wrapper.get('textarea').element as HTMLTextAreaElement
    textarea.setSelectionRange(25, 25)

    await wrapper.get('textarea').trigger('contextmenu', { clientX: 12, clientY: 12 })
    await wrapper.findAll('.markdown-context-parent').find((button) => button.text().includes('插入行'))?.trigger('click')
    const rowButton = wrapper.findAll('.markdown-context-submenu button').find((button) => button.text().includes('下方插入'))
    await rowButton?.trigger('click')

    expect((wrapper.props() as { modelValue: string }).modelValue).toBe('| A | B |\n| --- | --- |\n| 1 | 2 |\n|   |   |')
  })

  it('inserts a Markdown table column from the context menu', async () => {
    const wrapper = mountMarkdownEditor('| A | B |\n| --- | --- |\n| 1 | 2 |')
    const textarea = wrapper.get('textarea').element as HTMLTextAreaElement
    textarea.setSelectionRange(30, 30)

    await wrapper.get('textarea').trigger('contextmenu', { clientX: 12, clientY: 12 })
    await wrapper.findAll('.markdown-context-parent').find((button) => button.text().includes('插入列'))?.trigger('click')
    const columnButton = wrapper.findAll('.markdown-context-submenu button').find((button) => button.text().includes('右侧插入'))
    await columnButton?.trigger('click')

    expect((wrapper.props() as { modelValue: string }).modelValue).toBe('| A | B |   |\n| --- | --- | --- |\n| 1 | 2 |   |')
  })

  it('deletes a Markdown table row from the context menu', async () => {
    const wrapper = mountMarkdownEditor('| A | B |\n| --- | --- |\n| 1 | 2 |\n| 3 | 4 |')
    const textarea = wrapper.get('textarea').element as HTMLTextAreaElement
    textarea.setSelectionRange(25, 25)

    await wrapper.get('textarea').trigger('contextmenu', { clientX: 12, clientY: 12 })
    await wrapper.findAll('.markdown-context-parent').find((button) => button.text().includes('删除'))?.trigger('click')
    const rowButton = wrapper.findAll('.markdown-context-submenu button').find((button) => button.text().includes('删除整行'))
    await rowButton?.trigger('click')

    expect((wrapper.props() as { modelValue: string }).modelValue).toBe('| A | B |\n| --- | --- |\n| 3 | 4 |')
  })

  it('deletes a Markdown table column from the context menu', async () => {
    const wrapper = mountMarkdownEditor('| A | B | C |\n| --- | --- | --- |\n| 1 | 2 | 3 |')
    const textarea = wrapper.get('textarea').element as HTMLTextAreaElement
    textarea.setSelectionRange(8, 8)

    await wrapper.get('textarea').trigger('contextmenu', { clientX: 12, clientY: 12 })
    await wrapper.findAll('.markdown-context-parent').find((button) => button.text().includes('删除'))?.trigger('click')
    const columnButton = wrapper.findAll('.markdown-context-submenu button').find((button) => button.text().includes('删除整列'))
    await columnButton?.trigger('click')

    expect((wrapper.props() as { modelValue: string }).modelValue).toBe('| A | C |\n| --- | --- |\n| 1 | 3 |')
  })

  it('applies bold with Ctrl+B inside the editor', async () => {
    const wrapper = mountMarkdownEditor('hello')
    const textareaWrapper = wrapper.get('textarea')
    const textarea = textareaWrapper.element as HTMLTextAreaElement
    textarea.setSelectionRange(0, 5)

    await textareaWrapper.trigger('keydown', { key: 'b', ctrlKey: true })

    expect((wrapper.props() as { modelValue: string }).modelValue).toBe('**hello**')
  })

  it('wraps selected text when typing a Markdown pair symbol', async () => {
    const wrapper = mountMarkdownEditor('hello')
    const textareaWrapper = wrapper.get('textarea')
    const textarea = textareaWrapper.element as HTMLTextAreaElement
    textarea.setSelectionRange(0, 5)

    await textareaWrapper.trigger('keydown', { key: '*' })

    expect((wrapper.props() as { modelValue: string }).modelValue).toBe('*hello*')
  })

  it('opens find replace with Ctrl+F and replaces the current match', async () => {
    const wrapper = mountMarkdownEditor('alpha beta alpha')
    const textareaWrapper = wrapper.get('textarea')

    await textareaWrapper.trigger('keydown', { key: 'f', ctrlKey: true })
    const inputs = wrapper.findAll('.find-replace-bar input')
    await inputs[0]?.setValue('alpha')
    await inputs[1]?.setValue('omega')
    await wrapper.findAll('.find-replace-bar button').find((button) => button.text().includes('替换'))?.trigger('click')

    expect((wrapper.props() as { modelValue: string }).modelValue).toBe('omega beta alpha')
  })
})
