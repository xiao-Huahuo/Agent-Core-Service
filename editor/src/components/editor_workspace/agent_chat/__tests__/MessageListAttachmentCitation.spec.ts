/* Historical session attachment citation recovery tests. */
import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { describe, expect, it, vi } from 'vitest'

import MessageList from '../MessageList.vue'

describe('MessageList attachment citation recovery', () => {
  it('recovers exact session-upload URIs for old assistant messages', () => {
    Object.defineProperty(HTMLElement.prototype, 'scrollTo', { value: vi.fn(), configurable: true })
    const uri = 'session-upload://u1/library/s1/image11.png'
    const wrapper = mount(MessageList, {
      props: {
        messages: [
          {
            role: 'user',
            content: '这些图片有啥',
            attachments: [{
              attachment_id: 'att-1', user_id: 'u1', session_id: 's1', library_id: 'library', library_name: '',
              filename: 'image11.png', stored_name: 'image11.png', uri, mime_type: 'image/png', size: 12,
              source_type: 'image', created_at: '', metadata: {},
            }],
          },
          { role: 'assistant', content: '1. image11.png — Vue.js', node: 'agent', metadata: {} },
        ],
      },
      global: {
        plugins: [createPinia()],
        stubs: {
          MessageBubble: {
            props: ['message', 'citationMap'],
            template: '<div class="citation-map">{{ JSON.stringify(citationMap) }}</div>',
          },
          FinalTurnSummary: true,
          LoadingState: true,
          LoaderCube: true,
        },
      },
    })

    expect(wrapper.findAll('.citation-map')[1]?.text()).toContain(uri)
    expect(wrapper.findAll('.citation-map')[1]?.text()).toContain('image11.png')
  })
})
