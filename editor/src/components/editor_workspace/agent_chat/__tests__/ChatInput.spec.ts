/*
 * Chat input reference regression tests.
 *
 * Verifies that sending captures the visible reference before the input clears it.
 */
import { describe, expect, it } from 'vitest'

import { mount } from '@vue/test-utils'

import ChatInput from '../ChatInput.vue'

describe('ChatInput references', () => {
  it('emits a snapshot of the reference with the user prompt', async () => {
    const wrapper = mount(ChatInput, {
      props: {
        reference: '  被引用的文档内容  ',
      },
    })

    await wrapper.get('textarea').setValue('引用内容是什么意思?')
    await wrapper.get('textarea').trigger('keydown', { key: 'Enter' })

    expect(wrapper.emitted('send')).toEqual([
      ['引用内容是什么意思?', '被引用的文档内容'],
    ])
    expect(wrapper.emitted('clear-reference')).toHaveLength(1)
  })
})
