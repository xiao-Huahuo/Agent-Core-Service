/**
 * Daily activity heatmap card behavior tests.
 *
 * Usage:
 * Verifies the GitHub-style 52-week grid, filter-specific palette, and compact
 * summary metrics without launching the desktop interface.
 */

import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ActivityHeatmapCard from '@/components/dashboard/ActivityHeatmapCard.vue'

const { fetchActivityHeatmap } = vi.hoisted(() => ({ fetchActivityHeatmap: vi.fn() }))

vi.mock('@/api/activity', () => ({ fetchActivityHeatmap }))
vi.mock('@/stores/settings', () => ({
  useSettingsStore: () => ({ profile: { userId: 'u1' } }),
}))

describe('ActivityHeatmapCard', () => {
  beforeEach(() => {
    fetchActivityHeatmap.mockReset()
    fetchActivityHeatmap.mockResolvedValue({
      timezone: 'Asia/Shanghai',
      start_date: '2025-08-09',
      end_date: '2026-08-14',
      days: [
        {
          date: '2026-08-14',
          score: 8,
          level: 3,
          event_count: 3,
          modules: {
            library: { score: 3, event_count: 1 },
            agent: { score: 5, event_count: 2 },
          },
          activities: [
            { module: 'agent', action: 'agent_task_completed', score: 3, title: '完成 Agent 任务', created_at: '2026-08-14T08:00:00Z' },
          ],
        },
      ],
      summaries: {
        all: { total_score: 8, active_days: 1, current_streak: 1, peak_score: 8 },
        library: { total_score: 3, active_days: 1, current_streak: 1, peak_score: 3 },
        documents: { total_score: 0, active_days: 0, current_streak: 0, peak_score: 0 },
        knowledge: { total_score: 0, active_days: 0, current_streak: 0, peak_score: 0 },
        agent: { total_score: 5, active_days: 1, current_streak: 1, peak_score: 5 },
        tasks: { total_score: 0, active_days: 0, current_streak: 0, peak_score: 0 },
        other: { total_score: 0, active_days: 0, current_streak: 0, peak_score: 0 },
      },
    })
  })

  it('renders the supplied 52 by 7 contribution component with seven filters and four metrics', async () => {
    const wrapper = mount(ActivityHeatmapCard, {
      global: { stubs: { DashboardCardFrame: { template: '<section><slot /></section>' } } },
    })
    await flushPromises()

    expect(wrapper.findAll('[data-slot="contribution-graph-block"]')).toHaveLength(364)
    expect(wrapper.findAll('[data-slot="contribution-graph-group"]')).toHaveLength(52)
    expect(wrapper.find('.heat-grid').exists()).toBe(false)
    expect(wrapper.findAll('[data-slot="contribution-graph-block"][data-level="3"]')).toHaveLength(1)
    expect(wrapper.findAll('.filter-button')).toHaveLength(7)
    expect(wrapper.findAll('.metric-item')).toHaveLength(4)
    expect(wrapper.find('.weekday-labels').text()).toBe('一三五')
    expect(wrapper.findAll('.legend-cell')).toHaveLength(7)
    expect(wrapper.find('.contribution-legend').text()).toContain('少')
    expect(wrapper.find('.contribution-legend').text()).toContain('多')
    expect(wrapper.find('.day-detail').exists()).toBe(false)
    expect(wrapper.text()).toContain('每日活跃热力图')
    expect(wrapper.text()).toContain('活跃值')
  })

  it('switches the full-width heatmap to a filter-specific palette', async () => {
    const wrapper = mount(ActivityHeatmapCard, {
      global: { stubs: { DashboardCardFrame: { template: '<section><slot /></section>' } } },
    })
    await flushPromises()

    const totalPalette = wrapper.find('.activity-card').attributes('style')
    await wrapper.find('[data-filter="agent"]').trigger('click')
    const agentPalette = wrapper.find('.activity-card').attributes('style')

    expect(agentPalette).not.toBe(totalPalette)
    expect(wrapper.find('[data-filter="agent"]').classes()).toContain('active')
    expect(wrapper.text()).toContain('5')
    expect(wrapper.text()).not.toContain('完成 Agent 任务')
  })
})
