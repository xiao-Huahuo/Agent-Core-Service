/*
 * User chat bubble reference regression tests.
 *
 * Verifies that quoted document text is rendered with the user's message.
 */
import { describe, expect, it } from 'vitest'

import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import ChatBubble from '../ChatBubble.vue'
import MessageList from '../MessageList.vue'
import ToolBubble from '../ToolBubble.vue'
import { useWorkspaceStore } from '@/stores/workspace'

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

  it('renders assistant thinking duration above final content', () => {
    const wrapper = mount(ChatBubble, {
      global: {
        plugins: [createPinia()],
      },
      props: {
        message: {
          role: 'assistant',
          content: '你好，我在。',
          node: 'agent',
          thinking_seconds: 3.6,
        },
        userAvatar: 'user.png',
        agentAvatar: 'agent.png',
        isStreaming: false,
      },
    })

    expect(wrapper.get('.thinking-summary').text()).toContain('思考了 3.6s')
  })

  it('shows assistant metadata only on the final answer of each user turn', () => {
    HTMLElement.prototype.scrollTo = () => {}
    const wrapper = mount(MessageList, {
      global: {
        plugins: [createPinia()],
      },
      props: {
        messages: [
          { role: 'user', content: '请开始' },
          { role: 'assistant', content: '中间进度', node: 'agent', thinking_seconds: 1.1 },
          { role: 'assistant', content: '', node: 'child_agent' },
          { role: 'assistant', content: '最终答案', node: 'agent', thinking_seconds: 2.2 },
          { role: 'user', content: '第二个问题' },
          { role: 'assistant', content: '第二轮答案', node: 'agent', thinking_seconds: 3.3 },
        ],
        isStreaming: false,
      },
    })

    expect(wrapper.findAll('.message-actions')).toHaveLength(2)
    expect(wrapper.findAll('.thinking-summary').map((item) => item.text().replace(/\s+/g, ' ').trim())).toEqual([
      '思考了 2.2s',
      '思考了 3.3s',
    ])
  })

  it('keeps one avatar on the latest assistant item in a user turn', () => {
    HTMLElement.prototype.scrollTo = () => {}
    const wrapper = mount(MessageList, {
      global: { plugins: [createPinia()] },
      props: {
        messages: [
          { role: 'user', content: '请开始' },
          { role: 'assistant', content: '中间进度', node: 'agent' },
          { role: 'assistant', content: '最终答案', node: 'agent' },
        ],
      },
    })

    expect(wrapper.findAll('img[alt="agent"]')).toHaveLength(1)
  })

  it('keeps the avatar on a completed final assistant reply', () => {
    HTMLElement.prototype.scrollTo = () => {}
    const wrapper = mount(MessageList, {
      global: { plugins: [createPinia()] },
      props: {
        messages: [
          { role: 'user', content: '请开始' },
          { role: 'assistant', content: '中间进度', node: 'agent' },
          { role: 'assistant', content: '最终答案', node: 'agent' },
        ],
        isStreaming: false,
      },
    })

    expect(wrapper.findAll('img[alt="agent"]')).toHaveLength(1)
  })

  it('keeps an empty avatar column for consecutive assistant entries', () => {
    const wrapper = mount(ToolBubble, {
      global: { plugins: [createPinia()] },
      props: {
        message: { role: 'assistant', content: '中间输出' },
        userAvatar: 'user.png',
        agentAvatar: 'agent.png',
        showAvatar: false,
      },
    })

    expect(wrapper.find('.avatar-slot').exists()).toBe(true)
    expect(wrapper.find('img[alt="agent"]').exists()).toBe(false)
  })

  it('shows the pixel loading state before the assistant placeholder arrives', () => {
    HTMLElement.prototype.scrollTo = () => {}
    const wrapper = mount(MessageList, {
      global: { plugins: [createPinia()] },
      props: {
        messages: [{ role: 'user', content: '请开始' }],
        isStreaming: true,
      },
    })

    expect(wrapper.find('.loading-state').exists()).toBe(true)
    expect(wrapper.find('.loading-state__label').classes()).toContain('thinking-shimmer-text')
    expect(wrapper.findAll('.pixel')).toHaveLength(9)
    expect(wrapper.find('.thinking-spinner svg').exists()).toBe(true)
    expect(wrapper.find('.thinking-loader').exists()).toBe(false)
  })

  it('shows the pixel loading state instead of a cursor for an empty assistant stream', () => {
    const wrapper = mount(ChatBubble, {
      global: { plugins: [createPinia()] },
      props: {
        message: { role: 'assistant', content: '' },
        userAvatar: 'user.png',
        agentAvatar: 'agent.png',
        isStreaming: true,
        showAvatar: true,
      },
    })

    expect(wrapper.find('.loading-state').exists()).toBe(true)
    expect(wrapper.find('.cursor').exists()).toBe(false)
    expect(wrapper.find('.bubble.assistant').exists()).toBe(false)
  })

  it('shows the pixel loading state instead of a cursor in tool mode', () => {
    const wrapper = mount(ToolBubble, {
      global: { plugins: [createPinia()] },
      props: {
        message: { role: 'assistant', content: '' },
        userAvatar: 'user.png',
        agentAvatar: 'agent.png',
        isStreaming: true,
        showAvatar: true,
      },
    })

    expect(wrapper.find('.loading-state').exists()).toBe(true)
    expect(wrapper.find('.cursor').exists()).toBe(false)
    expect(wrapper.find('.assistant-article').exists()).toBe(false)
    expect(wrapper.get('.avatar').attributes('src')).toBe('agent.png')
  })

  it('reveals sources and message actions only after streaming completes', async () => {
    const wrapper = mount(ChatBubble, {
      global: { plugins: [createPinia()] },
      props: {
        message: { role: 'assistant', content: '带来源的回答' },
        userAvatar: 'user.png',
        agentAvatar: 'agent.png',
        isStreaming: true,
        knowledgeSources: [{ source_uri: 'notes/source.md', title: '来源文档', content: '' }],
      },
    })

    expect(wrapper.find('.message-actions').exists()).toBe(false)
    expect(wrapper.find('.knowledge-sources').exists()).toBe(false)

    await wrapper.setProps({ isStreaming: false })

    expect(wrapper.find('.message-actions').exists()).toBe(true)
    expect(wrapper.find('.knowledge-sources').exists()).toBe(true)
  })

  it('opens HTTP [N] citations in the shared right-side browser', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const wrapper = mount(ChatBubble, {
      global: { plugins: [pinia] },
      props: {
        message: { role: 'assistant', content: '网页来源 [1]', node: 'agent' },
        userAvatar: 'user.png',
        agentAvatar: 'agent.png',
        citationMap: { 1: { source_uri: 'https://example.com/source', content: '' } },
      },
    })

    await wrapper.get('.citation-anchor').trigger('click')

    const workspaceStore = useWorkspaceStore()
    expect(workspaceStore.browserSidebarOpen).toBe(true)
    expect(workspaceStore.browserSidebarUrl).toBe('https://example.com/source')
  })
})
