/*
 * Debug page session initialization regression tests.
 *
 * Usage:
 * Ensures an empty session response does not create a reactive request loop.
 */
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { listSessions } from '@/api/session'
import { useSettingsStore } from '@/stores/settings'
import DebugView from '@/views/DebugView.vue'

vi.mock('@/api/session', () => ({
  clearAllSessions: vi.fn(),
  createSession: vi.fn(),
  deleteSession: vi.fn(),
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
})
