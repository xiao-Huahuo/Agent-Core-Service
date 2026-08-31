/*
 * Debug action detail completeness tests.
 *
 * Clicking an action step must reveal the exact arguments and raw result rather
 * than only the shortened preview text.
 */
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import ThinkingSteps from '@/components/chat/ThinkingSteps.vue'

describe('ThinkingSteps action details', () => {
  it('reveals complete tool arguments and result content', async () => {
    const fullGoal = `完整参数-${'A'.repeat(400)}`
    const fullResult = `完整返回-${'R'.repeat(400)}`
    const wrapper = mount(ThinkingSteps, {
      props: {
        defaultExpanded: true,
        traces: [{
          node: 'action',
          event: 'tool_call_end',
          human_readable: '工具已完成。',
          tool_args_summary: 'goal=完整参数…',
          tool_args: { goal: fullGoal },
          raw_content: fullResult,
        }],
      },
    })

    await wrapper.find('.step-header').trigger('click')

    expect(wrapper.text()).toContain(fullGoal)
    expect(wrapper.text()).toContain(fullResult)
  })
})
