/*
 * ToolCallInline render tests.
 *
 * Usage:
 * Ensures action-node tool traces remain visible even when the tool is not in
 * the small legacy memory/knowledge allowlist.
 */

import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import ToolCallInline from '../ToolCallInline.vue'

describe('ToolCallInline', () => {
  it('renders backend human readable text for search-like tools', () => {
    const wrapper = mount(ToolCallInline, {
      props: {
        traces: [
          {
            event: 'tool_call_end',
            tool_name: 'web_search',
            display_name: '搜索',
            human_readable: '搜索到 3 个内容',
            result_count: 3,
          },
        ],
      },
    })

    expect(wrapper.text()).toContain('搜索到 3 个内容')
  })

  it('falls back to the tool name when no display metadata exists', () => {
    const wrapper = mount(ToolCallInline, {
      props: {
        traces: [
          {
            event: 'tool_call_end',
            tool_name: 'custom_tool',
          },
        ],
      },
    })

    expect(wrapper.text()).toContain('custom_tool')
  })
})
