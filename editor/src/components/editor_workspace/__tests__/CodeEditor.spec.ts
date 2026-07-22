/*
 * Markdown editor context-menu regression tests.
 *
 * Verifies that Markdown-only right-click commands transform the textarea
 * selection instead of depending on the browser's native context menu.
 */
import { describe, expect, it } from 'vitest'

import { mount } from '@vue/test-utils'

import CodeEditor from '../CodeEditor.vue'

function mountMarkdownEditor(value: string) {
  let wrapper!: ReturnType<typeof mount>
  wrapper = mount(CodeEditor, {
    props: {
      modelValue: value,
      language: 'md',
      'onUpdate:modelValue': (nextValue: string) => wrapper.setProps({ modelValue: nextValue }),
    },
  })
  return wrapper
}

describe('CodeEditor Markdown context menu', () => {
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
