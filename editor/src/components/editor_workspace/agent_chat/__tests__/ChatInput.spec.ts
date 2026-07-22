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

  it('emits the selected Agent access mode from the permission menu', async () => {
    const wrapper = mount(ChatInput, {
      props: {
        agentAccessMode: 'sandbox',
      },
    })

    await wrapper.get('.access-mode-trigger').trigger('click')
    const fullAccessButton = wrapper
      .findAll('.access-mode-option')
      .find((button) => button.text().includes('完全访问'))

    expect(fullAccessButton).toBeTruthy()
    await fullAccessButton?.trigger('click')

    expect(wrapper.emitted('set-agent-access-mode')).toEqual([['full_access']])
  })
})
