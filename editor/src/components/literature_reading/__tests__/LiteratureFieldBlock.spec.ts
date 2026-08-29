/*
 * Literature field interaction regression tests.
 *
 * Usage:
 * Run with Vitest to verify that empty editable fields enter editing directly
 * from their add control without requiring a second double-click.
 */

import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import LiteratureFieldBlock from '@/components/literature_reading/LiteratureFieldBlock.vue'
import type { SmartColumn } from '@/components/smart_forms/smartLiteratureTable'

describe('LiteratureFieldBlock', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('opens and focuses an empty Markdown field from the add button', async () => {
    const column = {
      id: 'core_content',
      title: '核心内容',
      type: 'text',
      editable: true,
    } as SmartColumn
    const wrapper = mount(LiteratureFieldBlock, {
      attachTo: document.body,
      props: {
        column,
        cell: { value: '' },
        markdownPath: 'papers/demo.md',
      },
      global: {
        stubs: {
          MarkdownContent: { template: '<div class="markdown-body"></div>' },
          IcIcon: { template: '<span />' },
        },
      },
    })

    await wrapper.get('.field-actions button').trigger('click')
    await flushPromises()

    const textarea = wrapper.get('textarea').element as HTMLTextAreaElement
    expect(textarea.style.display).toBe('')
    expect(document.activeElement).toBe(textarea)
    wrapper.unmount()
  })
})
