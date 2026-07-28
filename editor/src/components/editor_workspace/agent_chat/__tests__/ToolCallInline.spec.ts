/*
 * Tool call inline summary tests.
 *
 * Usage:
 * Verifies per-tool toolbar summary text without changing the existing trace
 * grouping or streaming lifecycle behavior.
 */
import { describe, expect, it } from 'vitest'

import { mount } from '@vue/test-utils'

import ToolCallInline from '../ToolCallInline.vue'

describe('ToolCallInline summaries', () => {
  it('shows count-based knowledge and file summaries', () => {
    const wrapper = mount(ToolCallInline, {
      props: {
        traces: [
          {
            event: 'tool_call_end',
            tool_name: 'get_knowledge_context',
            display_name: '检索知识',
            result_count: 4,
            raw_content: '1. [K1] 来源: a.md\n内容: A',
          },
          {
            event: 'tool_call_end',
            tool_name: 'search_knowledge',
            display_name: '全库联合搜索',
            tool_args_summary: 'query=原神',
            result_count: 2,
            raw_content: '=== 文件名匹配 ===\n  [K1] 原神.md',
          },
          {
            event: 'tool_call_end',
            tool_name: 'list_knowledge_files',
            display_name: '列出文件',
            raw_content: '[DIR] docs\n[FILE] docs/a.md\n[FILE] b.txt',
          },
        ],
      },
    })

    const text = wrapper.text()
    expect(text).toContain('检索到 4 条知识')
    expect(text).toContain('全库联合搜索：2 条结果 | 原神')
    expect(text).toContain('列出 2 个文件 / 1 个文件夹')
  })

  it('shows current status and content labels', () => {
    const wrapper = mount(ToolCallInline, {
      props: {
        traces: [
          {
            event: 'tool_call_end',
            tool_name: 'get_current_time',
            display_name: '获取当前时间',
            raw_content: '2026-07-28T13:42:00+08:00',
          },
          {
            event: 'tool_call_end',
            tool_name: 'get_current_viewing_document',
            display_name: '获取当前文档',
            raw_content: JSON.stringify({ name: '计划.md', path: 'docs/计划.md' }),
          },
          {
            event: 'tool_call_end',
            tool_name: 'use_skill',
            display_name: '使用技能',
            tool_args_summary: 'skill_ref=pdf',
            raw_content: 'Skill loaded: pdf',
          },
          {
            event: 'tool_call_end',
            tool_name: 'add_todo',
            display_name: '新增待办',
            tool_args_summary: 'text=整理测试报告',
            raw_content: '已创建待办 [todo_1]: 整理测试报告',
          },
        ],
      },
    })

    const text = wrapper.text()
    expect(text).toContain('获取当前时间：2026-07-28 13:42')
    expect(text).toContain('获取当前文档：计划.md')
    expect(text).toContain('使用技能：pdf')
    expect(text).toContain('新增待办：整理测试报告')
  })
})
