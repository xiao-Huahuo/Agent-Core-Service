/*
 * Tool mode user bubble reference regression tests.
 *
 * Verifies that quoted document text is rendered with the user's message when
 * the editor Agent panel is in tool mode.
 */
import { describe, expect, it } from 'vitest'

import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'

import ToolBubble from '../ToolBubble.vue'
import ToolCallInline from '../ToolCallInline.vue'

describe('ToolBubble user references', () => {
  it('renders the reference above the user message', () => {
    const wrapper = mount(ToolBubble, {
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
    expect(userBubble.text()).toBe('请解释这段话')
  })
})

describe('ToolCallInline action rows', () => {
  it('renders each tool call as an independent action row', () => {
    const wrapper = mount(ToolCallInline, {
      props: {
        traces: [
          {
            event: 'tool_call_end',
            tool_name: 'list_knowledge_files',
            display_name: '列出文件',
            result_count: 2,
            raw_content: '[FILE] a.md\n[FILE] b.md',
          },
          {
            event: 'tool_call_end',
            tool_name: 'web_search',
            display_name: '联网搜索',
            result_count: 3,
            tool_args_summary: 'query=原神',
            raw_content: '搜索结果',
          },
        ],
      },
    })

    expect(wrapper.findAll('.tool-call-box')).toHaveLength(2)
    expect(wrapper.findAll('.action-row')).toHaveLength(2)
    expect(wrapper.html()).toContain('列出 2 个文件')
    expect(wrapper.html()).toContain('联网搜索：3 条结果 | 原神')
  })
})
