/*
 * Agent 对话区可折叠条回归测试。
 *
 * 用途：验证思考条收起时不挂载持续增长的全文，工具条与子 Agent 条仍保留
 * 原有折叠交互，并核对思考摘要遵循 DSH 的首行/最新行规则。
 */
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import ChildAgentEventInline from '../ChildAgentEventInline.vue'
import ThinkRow from '../ThinkRow.vue'
import ToolCallInline from '../ToolCallInline.vue'

const iconStub = {
  props: ['name', 'size'],
  template: '<i class="stub-icon" :data-icon="name" :data-size="size"></i>',
}

describe('Agent chat collapsible rows', () => {
  it('mounts the Think body only while expanded and follows the DSH summary rule', async () => {
    const wrapper = mount(ThinkRow, {
      global: { stubs: { IcIcon: iconStub } },
      props: { text: '第一行\n正在快速生成的最新一行', running: true },
    })

    expect(wrapper.get('.think-row__leading .stub-icon').attributes('data-size')).toBe('15')
    expect(wrapper.get('.think-row__summary').text()).toBe('正在快速生成的最新一行')
    expect(wrapper.get('.think-row__collapse').classes()).not.toContain('expanded')
    expect(wrapper.find('.think-row__body').exists()).toBe(false)

    await wrapper.get('.think-row__trigger').trigger('click')
    expect(wrapper.get('.think-row__trigger').attributes('aria-expanded')).toBe('true')
    expect(wrapper.get('.think-row__collapse').classes()).toContain('expanded')
    expect(wrapper.get('.think-row__body').text()).toBe('第一行\n正在快速生成的最新一行')

    await wrapper.setProps({ running: false })
    expect(wrapper.get('.think-row__summary').text()).toBe('第一行')
  })

  it('keeps tool result content mounted while collapsed', async () => {
    const wrapper = mount(ToolCallInline, {
      global: { stubs: { IcIcon: iconStub } },
      props: {
        traces: [{
          event: 'tool_call_end',
          tool_call_id: 'call-1',
          tool_name: 'get_current_time',
          display_name: '获取当前时间',
          raw_content: '2026-08-30T10:00:00+08:00',
        }],
      },
    })

    expect(wrapper.get('.tool-result-collapse').classes()).not.toContain('open')
    expect(wrapper.find('.tool-result-content').exists()).toBe(true)

    await wrapper.get('.tool-expand-btn').trigger('click')
    expect(wrapper.get('.tool-result-collapse').classes()).toContain('open')
  })

  it('toggles the retained child Agent detail region', async () => {
    const wrapper = mount(ChildAgentEventInline, {
      global: { stubs: { IcIcon: iconStub } },
      props: {
        event: {
          event_name: 'child_agent.started',
          child: {
            run_id: 'child-run-1',
            goal: '检查展开动效',
            mode: 'background',
            status: 'running',
            access_mode: 'readonly',
            allowed_tools: [],
          },
        },
      },
    })

    expect(wrapper.get('.child-agent-event-detail').classes()).not.toContain('expanded')
    await wrapper.get('.child-agent-event-head').trigger('click')
    expect(wrapper.get('.child-agent-event-detail').classes()).toContain('expanded')
  })
})
