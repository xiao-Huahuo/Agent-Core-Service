/** Shared editor toolbar contract tests. */
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import EditorPaneToolbar from '@/components/editor_workspace/EditorPaneToolbar.vue'

describe('EditorPaneToolbar', () => {
  it('shares localized modes and a working save action across editor panes', async () => {
    const wrapper = mount(EditorPaneToolbar, {
      props: {
        title: '示例.md',
        modelValue: 'edit',
        options: [
          { mode: 'edit', label: '编辑', icon: 'edit' },
          { mode: 'preview', label: '预览', icon: 'visibility' },
        ],
        saveLabel: '保存',
      },
    })

    expect(wrapper.text()).toContain('示例.md')
    expect(wrapper.findAll('.editor-mode-switch button').map((button) => button.text())).toEqual(['编辑', '预览'])
    await wrapper.get('.editor-pane-save').trigger('click')
    expect(wrapper.emitted('save')).toHaveLength(1)
  })
})
