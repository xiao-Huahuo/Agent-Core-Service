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
import activityBarSource from '@/components/editor_workspace/ActivityBar.vue?raw'
import editorWorkspaceSource from '@/views/EditorWorkspace.vue?raw'

vi.mock('@/components/common/IcIcon.vue', () => ({
  default: { template: '<span />' },
}))

describe('ActivityBar', () => {
  it('allocates a 50 percent wider column in management mode', () => {
    expect(editorWorkspaceSource).toContain('const ACTIVITY_BAR_MANAGEMENT_WIDTH = 204')
  })

  it('keeps management icons left aligned and labels centered', () => {
    expect(activityBarSource).toContain('.activity-bar.management .activity-button > :deep(.ic-icon:not(.knowledge-chevron))')
    expect(activityBarSource).toMatch(/\.activity-bar\.management \.activity-label \{[^}]*width: 100%;[^}]*text-align: center;/)
  })

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
    agentQueueActive: false,
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
    await wrapper.get('button[aria-label="库"]').trigger('click')

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

  it('keeps the submenu open after child navigation but lets the parent toggle it', async () => {
    const wrapper = mount(ActivityBar, { props: { ...props, displayMode: 'management' } })
    const knowledgeButton = wrapper.get('button[aria-label="库"]')

    await knowledgeButton.trigger('click')
    expect(wrapper.find('[aria-label="知识库菜单"]').exists()).toBe(true)

    await wrapper.get('button[aria-label="图书馆"]').trigger('click')
    expect(wrapper.emitted('openLibrary')).toHaveLength(1)
    expect(wrapper.find('[aria-label="知识库菜单"]').exists()).toBe(true)

    await knowledgeButton.trigger('click')
    expect(wrapper.find('[aria-label="知识库菜单"]').exists()).toBe(false)
  })

  it('marks the knowledge group active when a child view is active', () => {
    const wrapper = mount(ActivityBar, { props: { ...props, libraryActive: true } })

    expect(wrapper.get('button[aria-label="库"]').classes()).toContain('active')
  })

  it('moves one shared hover indicator to the pointed navigation button', async () => {
    const wrapper = mount(ActivityBar, { props })
    const activityBar = wrapper.get('.activity-bar')
    const filesButton = wrapper.get('button[aria-label="Files"]')
    vi.spyOn(activityBar.element, 'getBoundingClientRect').mockReturnValue({ top: 10 } as DOMRect)
    vi.spyOn(filesButton.element, 'getBoundingClientRect').mockReturnValue({ top: 58 } as DOMRect)

    await filesButton.trigger('mouseover')

    const indicator = wrapper.get('.activity-hover-indicator')
    expect(indicator.attributes('style')).toContain('translate3d(0, 48px, 0)')
    expect(indicator.attributes('style')).toContain('opacity: 1')

    await activityBar.trigger('mouseleave')
    expect(indicator.attributes('style')).toContain('opacity: 0')
  })

  it('moves a shared hover indicator between knowledge submenu items', async () => {
    const wrapper = mount(ActivityBar, { props: { ...props, displayMode: 'management' } })
    await wrapper.get('button[aria-label="库"]').trigger('click')

    const submenu = wrapper.get('[aria-label="知识库菜单"]')
    const libraryButton = wrapper.get('button[aria-label="图书馆"]')
    vi.spyOn(submenu.element, 'getBoundingClientRect').mockReturnValue({ top: 100 } as DOMRect)
    vi.spyOn(libraryButton.element, 'getBoundingClientRect').mockReturnValue({ top: 144 } as DOMRect)

    await libraryButton.trigger('mouseover')

    const indicator = wrapper.get('.knowledge-hover-indicator')
    expect(indicator.attributes('style')).toContain('translate3d(0, 44px, 0)')
    expect(indicator.attributes('style')).toContain('opacity: 1')
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
