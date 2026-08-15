/**
 * Dashboard time-and-consumption panel regression tests.
 *
 * Usage: verifies that the removed recent-conversation block does not return.
 */

import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import TimeConsumptionPanel from '@/components/dashboard/TimeConsumptionPanel.vue'

vi.mock('vue-echarts', () => ({ default: { template: '<div />' } }))
vi.mock('echarts', () => ({}))
vi.mock('@/api/library', () => ({
  listLibraryItems: vi.fn<() => Promise<{ items: never[] }>>().mockResolvedValue({ items: [] }),
}))
vi.mock('@/stores/settings', () => ({
  useSettingsStore: () => ({ profile: { userId: 'u1' } }),
}))
vi.mock('@/stores/workspace', () => ({
  useWorkspaceStore: () => ({
    flatNodes: [],
    loadKnowledgeTree: vi.fn<() => void>(),
  }),
}))

describe('TimeConsumptionPanel', () => {
  it('does not render the recent Agent conversation block', async () => {
    const wrapper = mount(TimeConsumptionPanel, {
      global: {
        stubs: {
          VChart: true,
          RagMetricsCard: true,
          TokenUsageCard: true,
          LatencyCard: true,
          ActivityHeatmapCard: true,
        },
      },
    })
    await flushPromises()

    expect(wrapper.find('.agent-session-list').exists()).toBe(false)
  })
})
