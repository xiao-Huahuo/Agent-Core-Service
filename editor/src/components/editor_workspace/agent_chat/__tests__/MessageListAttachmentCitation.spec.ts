/* Historical session attachment citation recovery tests. */
import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { describe, expect, it, vi } from 'vitest'

import MessageList from '../MessageList.vue'

describe('MessageList attachment citation recovery', () => {
  it('coalesces repeated scroll events into one animation-frame layout read', async () => {
    Object.defineProperty(HTMLElement.prototype, 'scrollTo', { value: vi.fn(), configurable: true })
    const callbacks: FrameRequestCallback[] = []
    const frameSpy = vi.spyOn(window, 'requestAnimationFrame').mockImplementation((callback) => {
      callbacks.push(callback)
      return callbacks.length
    })
    const wrapper = mount(MessageList, {
      props: { messages: [] },
      global: {
        plugins: [createPinia()],
        stubs: { MessageBubble: true, FinalTurnSummary: true, LoadingState: true, LoaderCube: true },
      },
    })

    await wrapper.get('.message-list').trigger('scroll')
    await wrapper.get('.message-list').trigger('scroll')
    await wrapper.get('.message-list').trigger('scroll')

    expect(callbacks).toHaveLength(1)
    callbacks[0]?.(performance.now())
    wrapper.unmount()
    frameSpy.mockRestore()
  })

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

  it('mounts only four-library results cited by the final Agent answer', () => {
    Object.defineProperty(HTMLElement.prototype, 'scrollTo', { value: vi.fn(), configurable: true })
    const wrapper = mount(MessageList, {
      props: {
        messages: [{
          role: 'assistant',
          content: '建议使用这个组件 [K2]',
          node: 'agent',
          metadata: {
            citation_map: {
              K1: {
                source_uri: 'docs/a.md', content: '文件', source: 'tool',
                search_result: { id: 'docs/a.md', source: 'files', title: 'a.md', snippet: '', locator: 'docs/a.md', updated_at: '', score: 1, matched_modes: ['title'], item: {} },
              },
              K2: {
                source_uri: 'cards/a.vue', content: '组件', source: 'tool',
                search_result: { id: 'cards/a.vue', source: 'components', title: 'Card', snippet: '', locator: 'cards/a.vue', updated_at: '', score: 1, matched_modes: ['title'], item: {} },
              },
            },
          },
        }],
      },
      global: {
        plugins: [createPinia()],
        stubs: {
          MessageBubble: true,
          FinalTurnSummary: true,
          AgentSearchResultBlocks: {
            props: ['results'],
            template: '<div class="mounted-results">{{ results.map((item) => item.id).join(",") }}</div>',
          },
          LoadingState: true,
          LoaderCube: true,
        },
      },
    })

    expect(wrapper.get('.mounted-results').text()).toBe('cards/a.vue')
  })
})
