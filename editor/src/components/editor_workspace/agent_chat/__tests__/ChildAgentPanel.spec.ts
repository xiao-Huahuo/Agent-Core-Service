/*
 * 子 Agent 面板详情链接回归测试。
 *
 * 用途：验证名字链接打开指定完整对话，并在主历史恢复时并发预载全部子 Session。
 */
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ChildAgentPanel from '../ChildAgentPanel.vue'

const mocks = vi.hoisted(() => ({
  fetchChildAgents: vi.fn(),
  fetchChildAgentDshWeb: vi.fn(),
  preload: vi.fn(),
}))

vi.mock('@/api/agent', () => ({
  fetchChildAgents: mocks.fetchChildAgents,
  fetchChildAgentDshWeb: mocks.fetchChildAgentDshWeb,
  stopChildAgent: vi.fn(),
}))
vi.mock('@/components/editor_workspace/agent_chat/childAgentConversations', () => ({
  preloadChildAgentConversations: mocks.preload,
}))

describe('ChildAgentPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.fetchChildAgents.mockResolvedValue({
      children: [{
        run_id: 'child-1', conversation_session_id: 'child-session-1', parent_run_id: 'parent-1',
        goal: '检索资料', name: 'explore1', category: 'explore', mode: 'background', status: 'running',
        access_mode: 'readonly', allowed_tools: [],
      }],
    })
    mocks.fetchChildAgentDshWeb.mockResolvedValue({ run_id: 'child-1', url: 'http://127.0.0.1:3080/#readonly=1' })
  })

  it('renders the child name as a link and opens its complete conversation', async () => {
    const wrapper = mount(ChildAgentPanel, { props: { sessionId: 'parent-session', userId: 'u1' } })
    await flushPromises()

    const link = wrapper.get('.child-agent-name-link')
    expect(link.text()).toBe('explore1')
    await link.trigger('click')
    expect(wrapper.emitted('open-conversation')?.[0]?.[0]).toMatchObject({ run_id: 'child-1' })
    expect(mocks.preload).toHaveBeenCalledWith(
      [expect.objectContaining({ conversation_session_id: 'child-session-1' })],
      'u1',
    )
  })

  it('opens DSH provider runs in their managed Web URL', async () => {
    const openExternal = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(window, 'agentEditorDesktop', {
      configurable: true,
      value: { openExternal },
    })
    mocks.fetchChildAgents.mockResolvedValue({
      children: [{
        run_id: 'child-dsh', conversation_session_id: 'child-session-dsh', parent_run_id: 'parent-1',
        goal: '修改代码', name: 'dsh1', category: 'dsh', provider: 'dsh', mode: 'background', status: 'running',
        access_mode: 'sandbox', allowed_tools: ['dsh.edit'],
      }],
    })
    mocks.fetchChildAgentDshWeb.mockResolvedValue({ run_id: 'child-dsh', url: 'http://127.0.0.1:3080/#readonly=1' })

    const wrapper = mount(ChildAgentPanel, { props: { sessionId: 'parent-session', userId: 'u1' } })
    await flushPromises()
    await wrapper.get('.child-agent-name-link').trigger('click')
    await flushPromises()

    expect(mocks.fetchChildAgentDshWeb).toHaveBeenCalledWith('child-dsh', 'u1', 'parent-session')
    expect(openExternal).toHaveBeenCalledWith('http://127.0.0.1:3080/#readonly=1')
    expect(wrapper.emitted('open-conversation')).toBeUndefined()
  })
})
