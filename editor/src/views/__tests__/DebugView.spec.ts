/*
 * Debug page session initialization regression tests.
 *
 * Usage:
 * Ensures an empty session response does not create a reactive request loop.
 */
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { fetchMessages, fetchSessionState, listSessions } from '@/api/session'
import { useChatStore } from '@/stores/chat'
import { useSettingsStore } from '@/stores/settings'
import DebugView from '@/views/DebugView.vue'

vi.mock('@/api/session', () => ({
  clearAllSessions: vi.fn(),
  createSession: vi.fn(),
  deleteSession: vi.fn(),
  fetchMessages: vi.fn().mockResolvedValue([]),
  fetchSessionState: vi.fn().mockResolvedValue({ session_state: null }),
  listSessions: vi.fn().mockResolvedValue([]),
  pruneEmptySessions: vi.fn(),
  updateSessionName: vi.fn(),
}))

describe('DebugView session initialization', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('loads an empty session list once without starting a request loop', async () => {
    useSettingsStore().setUserId('1')

    const wrapper = mount(DebugView, {
      global: {
        stubs: {
          AgentTracePanel: true,
          GlobalConstantsPanel: true,
          IcIcon: true,
          MemoryKnowledgePanel: true,
          MultimodalIngestionPanel: true,
          RuntimeApisPanel: true,
          ToolRegistryPanel: true,
        },
      },
    })

    await flushPromises()
    await flushPromises()

    expect(listSessions).toHaveBeenCalledTimes(1)
    expect(listSessions).toHaveBeenCalledWith('1')

    wrapper.unmount()
  })

  it('opens the read-only global constants subpage from the debug tabs', async () => {
    const wrapper = mount(DebugView, {
      global: {
        stubs: {
          AgentTracePanel: true,
          GlobalConstantsPanel: true,
          IcIcon: true,
          MemoryKnowledgePanel: true,
          MultimodalIngestionPanel: true,
          RuntimeApisPanel: true,
          ToolRegistryPanel: true,
        },
      },
    })

    const constantsTab = wrapper.findAll('button').find(button => button.text().includes('全局常量'))
    expect(constantsTab).toBeDefined()
    expect(constantsTab!.findComponent({ name: 'IcIcon' }).props('name')).toBe('tune')
    await constantsTab!.trigger('click')

    expect(wrapper.findComponent({ name: 'GlobalConstantsPanel' }).exists()).toBe(true)
  })

  it('restores the exact model request snapshots for the selected debug session', async () => {
    useSettingsStore().setUserId('1')
    vi.mocked(listSessions).mockResolvedValue([{
      session_id: 'session-1',
      user_id: '1',
      session_name: '真实会话',
      created_at: '2026-08-31T00:00:00Z',
      updated_at: '2026-08-31T00:00:00Z',
    }])
    vi.mocked(fetchMessages).mockResolvedValue([])
    vi.mocked(fetchSessionState).mockResolvedValue({
      session_state: {
        context_snapshots: [{
          call_index: 1,
          node: 'agent',
          model_tier: 'large',
          model: 'deepseek-v4-flash',
          temperature: 0,
          timeout_seconds: 120,
          model_kwargs: {},
          messages: [{ role: 'user', content: '真实请求' }],
          tools: [],
        }],
      },
    })

    const wrapper = mount(DebugView, {
      global: { stubs: { AgentTracePanel: true, IcIcon: true } },
    })
    await flushPromises()
    await flushPromises()

    expect(fetchSessionState).toHaveBeenCalledWith('session-1')
    expect(useChatStore().contextSnapshots[0]?.messages).toEqual([{ role: 'user', content: '真实请求' }])
    wrapper.unmount()
  })
})
