/*
 * User chat bubble reference regression tests.
 *
 * Verifies that quoted document text is rendered with the user's message.
 */
import { describe, expect, it } from 'vitest'

import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'

import ChatBubble from '../ChatBubble.vue'

describe('ChatBubble user references', () => {
  it('renders the reference above the user message', () => {
    const wrapper = mount(ChatBubble, {
      global: {
        plugins: [createPinia()],
      },
      props: {
        message: {
          role: 'user',
          content: '请解释这段话',
          reference: '被引用的文档内容',
        },
        userAvatar: 'user.png',
        agentAvatar: 'agent.png',
      },
    })

    const referenceBlock = wrapper.get('.reference-block')
    const userBubble = wrapper.get('.bubble.user')
    expect(referenceBlock.text()).toBe('被引用的文档内容')
    expect(referenceBlock.element.compareDocumentPosition(userBubble.element) & Node.DOCUMENT_POSITION_FOLLOWING)
      .toBeTruthy()
    expect(wrapper.get('.bubble.user').text()).toBe('请解释这段话')
  })
})
