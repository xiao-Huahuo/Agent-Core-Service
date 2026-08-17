import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import EditorModeSwitch from '@/components/editor_workspace/EditorModeSwitch.vue'
import { resolveEditorFilePipeline } from '@/utils/editorFilePipeline'

describe('EditorModeSwitch', () => {
  it('renders only the modes supplied by the active file pipeline', async () => {
    const wrapper = mount(EditorModeSwitch, {
      props: {
        modelValue: 'text',
        options: [
          { mode: 'text', label: 'Text', icon: 'description' },
          { mode: 'forms', label: 'Forms', icon: 'table' },
        ],
      },
    })

    expect(wrapper.findAll('button').map((button) => button.text())).toEqual(['Text', 'Forms'])
    await wrapper.findAll('button')[1]?.trigger('click')
    expect(wrapper.emitted('update:modelValue')).toEqual([['forms']])
  })

  it('keeps Edit Preview Split as the default contract for search preview', () => {
    const wrapper = mount(EditorModeSwitch, { props: { modelValue: 'edit' } })

    expect(wrapper.findAll('button').map((button) => button.text())).toEqual(['Edit', 'Preview', 'Split'])
  })

  it('renders a real registered SVG for every modality mode icon', () => {
    const options = [
      ...resolveEditorFilePipeline('note.md').modes,
      ...resolveEditorFilePipeline('note.txt').modes,
      ...resolveEditorFilePipeline('data.csv').modes,
      ...resolveEditorFilePipeline('report.docx').modes,
      ...resolveEditorFilePipeline('script.py').modes,
      ...resolveEditorFilePipeline('legacy.doc').modes,
    ].filter((item, index, all) => all.findIndex((candidate) => candidate.mode === item.mode) === index)
    const wrapper = mount(EditorModeSwitch, { props: { modelValue: options[0]!.mode, options } })

    expect(wrapper.findAll('svg.ic-icon')).toHaveLength(options.length)
    expect(wrapper.findAll('svg.ic-icon').every((icon) => icon.element.childElementCount > 0)).toBe(true)
  })
})
