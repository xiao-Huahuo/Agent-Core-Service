/** Component detail borderless-control and shared-code-preview tests. */

import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import ComponentLibraryDetail from '@/components/component_library/ComponentLibraryDetail.vue'
import type { ComponentLibraryItem } from '@/types/componentLibrary'

const item: ComponentLibraryItem = {
  component_id: 'buttons/demo.vue',
  user_id: 'u1',
  title: '演示按钮',
  tag: 'buttons',
  source_format: 'vue',
  source: '<template><button>OK</button></template>',
  builtin: false,
  created_at: null,
  updated_at: null,
}

describe('ComponentLibraryDetail', () => {
  it('reuses the editor code preview and keeps copy icon-only', () => {
    const wrapper = mount(ComponentLibraryDetail, {
      props: { item },
      global: {
        stubs: {
          ComponentPreview: { template: '<div />' },
          CodePreview: {
            name: 'CodePreview',
            props: ['content', 'language'],
            template: '<div class="code-preview-stub" />',
          },
          IcIcon: { template: '<span />' },
        },
      },
    })

    expect(wrapper.getComponent({ name: 'CodePreview' }).props()).toMatchObject({
      content: item.source,
      language: 'vue',
    })
    expect(wrapper.get('.detail-copy-button').text()).toBe('')
  })

  it('exposes an icon-only delete action at the detail top right', async () => {
    const wrapper = mount(ComponentLibraryDetail, {
      props: { item },
      global: {
        stubs: {
          ComponentPreview: { template: '<div />' },
          CodePreview: { template: '<div />' },
          IcIcon: { template: '<span />' },
        },
      },
    })

    const deleteButton = wrapper.get('.detail-delete-button')
    expect(deleteButton.text()).toBe('')
    await deleteButton.trigger('click')
    expect(wrapper.emitted('delete')).toEqual([[item]])
  })

  it('reuses the code editor and emits edited source in sidebar mode', async () => {
    const wrapper = mount(ComponentLibraryDetail, {
      props: { item, editable: true, compact: true },
      global: {
        stubs: {
          ComponentPreview: { props: ['source'], template: '<div class="preview-source">{{ source }}</div>' },
          CodeEditor: {
            props: ['modelValue'],
            emits: ['update:modelValue'],
            template: '<button class="edit-source" @click="$emit(\'update:modelValue\', \'<template>changed</template>\')">edit</button>',
          },
          IcIcon: { template: '<span />' },
        },
      },
    })

    await wrapper.get('.edit-source').trigger('click')
    await wrapper.get('.detail-save-button').trigger('click')

    expect(wrapper.emitted('save')).toEqual([['<template>changed</template>']])
    expect(wrapper.get('.detail-workbench').classes()).toContain('compact')
  })
})
