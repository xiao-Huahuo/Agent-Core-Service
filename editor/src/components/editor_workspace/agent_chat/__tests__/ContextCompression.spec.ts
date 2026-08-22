/**
 * Context compression UI regression tests.
 *
 * Verifies that the meter consumes backend token usage and that synchronous
 * compression has a dedicated status bar independent from Agent thinking.
 */
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import ContextCompressionStatus from '@/components/editor_workspace/agent_chat/ContextCompressionStatus.vue'
import ContextProgress from '@/components/editor_workspace/agent_chat/ContextProgress.vue'

describe('context compression UI', () => {
  it('renders the exact backend-reported working-context ratio', () => {
    const wrapper = mount(ContextProgress, {
      props: { currentTokens: 48_000, maxContextTokens: 64_000 },
    })

    expect(wrapper.get('.pct').text()).toBe('75%')
    expect(wrapper.get('.context-progress').attributes('title')).toBe('48,000 / 64,000 tokens')
  })

  it('renders a dedicated synchronous compression status', () => {
    const wrapper = mount(ContextCompressionStatus)

    expect(wrapper.get('[role="status"]').text()).toContain('正在压缩上下文')
  })
})
