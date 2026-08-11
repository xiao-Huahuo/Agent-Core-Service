/**
 * Activity bar navigation tests.
 *
 * Usage:
 * Verifies the knowledge-base group keeps the existing navigation events
 * while exposing its child entries through the animated submenu.
 */
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ActivityBar from '@/components/editor_workspace/ActivityBar.vue'

vi.mock('@/components/common/IcIcon.vue', () => ({
  default: { template: '<span />' },
}))

describe('ActivityBar', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  const props = {
    displayMode: 'icons' as const,
    homeActive: false,
    fileOpen: false,
    gitActive: false,
    agentOpen: false,
    resourcesActive: false,
    favoritesActive: false,
    libraryActive: false,
    vaultActive: false,
    formsActive: false,
    ingestionActive: false,
    visualizationActive: false,
    agentActive: false,
    graphActive: false,
    dashboardActive: false,
    debugActive: false,
    feedbackOpen: false,
    searchActive: false,
    skillsActive: false,
    settingsActive: false,
  }

  it('opens knowledge submenu and preserves child navigation events', async () => {
    const wrapper = mount(ActivityBar, { props })

    expect(wrapper.find('[aria-label="知识库菜单"]').exists()).toBe(false)
    await wrapper.get('button[aria-label="知识库"]').trigger('click')

    expect(wrapper.find('[aria-label="知识库菜单"]').exists()).toBe(true)
    expect(wrapper.findAll('[aria-label="知识库菜单"] button')).toHaveLength(4)

    await wrapper.get('button[aria-label="智能表格"]').trigger('click')
    expect(wrapper.emitted('openForms')).toHaveLength(1)
    expect(wrapper.find('[aria-label="知识库菜单"]').exists()).toBe(false)
  })

  it('opens the capsule on hover in icon mode', async () => {
    const wrapper = mount(ActivityBar, { props })

    await wrapper.get('.knowledge-group').trigger('mouseenter')

    expect(wrapper.find('[aria-label="知识库菜单"]').exists()).toBe(true)
  })

  it('marks the knowledge group active when a child view is active', () => {
    const wrapper = mount(ActivityBar, { props: { ...props, libraryActive: true } })

    expect(wrapper.get('button[aria-label="知识库"]').classes()).toContain('active')
  })

  it('places ingestion, MD-HTML, and skills at the bottom of the main group', () => {
    const labels = wrapperLabels(mount(ActivityBar, { props }))

    expect(labels.indexOf('看板')).toBeLessThan(labels.indexOf('入库进度'))
    expect(labels.indexOf('入库进度')).toBeLessThan(labels.indexOf('MD-HTML'))
    expect(labels.indexOf('MD-HTML')).toBeLessThan(labels.indexOf('Skills'))
  })
})

function wrapperLabels(wrapper: ReturnType<typeof mount<typeof ActivityBar>>): string[] {
  return wrapper.findAll('.activity-bar > .activity-button').map((button) => button.attributes('aria-label') || '')
}
