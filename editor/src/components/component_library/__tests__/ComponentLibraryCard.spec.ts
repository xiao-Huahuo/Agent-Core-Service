/**
 * Component library card interaction and intrinsic-size tests.
 *
 * Usage:
 * Verifies that the preview remains interactive while only the top-right icon
 * opens details, and that iframe measurements determine the card height.
 */

import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import ComponentLibraryCard from '@/components/component_library/ComponentLibraryCard.vue'
import componentNameEditorSource from '@/components/component_library/ComponentNameEditor.vue?raw'
import type { ComponentLibraryItem } from '@/types/componentLibrary'

const item: ComponentLibraryItem = {
  component_id: 'builtin:button.vue',
  user_id: 'u1',
  title: '按钮',
  tag: 'buttons',
  source_format: 'vue',
  source: '<template><button>OK</button></template>',
  builtin: true,
  created_at: null,
  updated_at: null,
}

const drawingScriptItem = {
  ...item,
  component_id: 'drawing scripts/chart.script',
  title: '销售曲线',
  tag: 'drawing scripts',
  source_format: 'script',
  source: 'plt.plot([1, 2])',
  script_language: 'Python',
  cover_asset_id: '',
  cover_asset: null,
} as ComponentLibraryItem

describe('ComponentLibraryCard', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('keeps preview clicks separate from the top-right detail action', async () => {
    const wrapper = mount(ComponentLibraryCard, {
      props: { item },
      global: {
        stubs: {
          ComponentPreview: {
            name: 'ComponentPreview',
            template: '<button class="preview-stub">component action</button>',
          },
          IcIcon: { template: '<span />' },
        },
      },
    })

    await wrapper.get('.preview-stub').trigger('click')
    expect(wrapper.emitted('open')).toBeUndefined()

    await wrapper.get('.detail-button').trigger('click')
    expect(wrapper.emitted('open')).toEqual([[item]])
  })

  it('uses the measured component height instead of a fixed preview height', async () => {
    const wrapper = mount(ComponentLibraryCard, {
      props: { item },
      global: {
        stubs: {
          ComponentPreview: {
            name: 'ComponentPreview',
            emits: ['resize'],
            template: '<div class="preview-stub" />',
          },
          IcIcon: { template: '<span />' },
        },
      },
    })

    wrapper.getComponent({ name: 'ComponentPreview' }).vm.$emit('resize', { width: 160, height: 120 })
    await wrapper.vm.$nextTick()

    expect(wrapper.get('.preview-surface').attributes('style')).toContain('--component-preview-height: 184px')
  })

  it('does not resize or reset the preview when interaction changes width only', async () => {
    const wrapper = mount(ComponentLibraryCard, {
      props: { item },
      global: {
        stubs: {
          ComponentPreview: {
            name: 'ComponentPreview',
            emits: ['resize'],
            template: '<button class="preview-stub">component action</button>',
          },
          IcIcon: { template: '<span />' },
        },
      },
    })
    const preview = wrapper.getComponent({ name: 'ComponentPreview' })
    preview.vm.$emit('resize', { width: 160, height: 40 })
    await wrapper.vm.$nextTick()
    const stableStyle = wrapper.get('.preview-surface').attributes('style')

    preview.vm.$emit('resize', { width: 220, height: 40 })
    await wrapper.vm.$nextTick()

    expect(wrapper.get('.preview-surface').attributes('style')).toBe(stableStyle)
  })

  it('places borderless icon-only detail and copy actions together at top right', () => {
    const wrapper = mount(ComponentLibraryCard, {
      props: { item },
      global: {
        stubs: {
          ComponentPreview: { template: '<div />' },
          FavoriteButton: {
            name: 'FavoriteButton',
            props: ['targetType', 'targetId'],
            template: '<button class="favorite-stub" />',
          },
          IcIcon: { template: '<span />' },
        },
      },
    })

    expect(wrapper.get('.card-actions').findAll('button')).toHaveLength(3)
    expect(wrapper.getComponent({ name: 'FavoriteButton' }).props()).toMatchObject({
      targetType: 'component',
      targetId: item.component_id,
    })
    expect(wrapper.get('.copy-button').text()).toBe('')
    expect(wrapper.get('.component-meta').find('.copy-button').exists()).toBe(false)
  })

  it('places deletion at the card bottom right and emits the selected item', async () => {
    const wrapper = mount(ComponentLibraryCard, {
      props: { item },
      global: {
        stubs: {
          ComponentPreview: { template: '<div />' },
          IcIcon: { template: '<span />' },
        },
      },
    })

    const deleteButton = wrapper.get('.component-meta .delete-button')
    expect(deleteButton.attributes('aria-label')).toBe('删除组件')
    await deleteButton.trigger('click')
    expect(wrapper.emitted('delete')).toEqual([[item]])
  })

  it('supports keyboard-confirmed inline renaming without opening details', async () => {
    const wrapper = mount(ComponentLibraryCard, {
      props: { item },
      global: {
        stubs: {
          ComponentPreview: { template: '<div />' },
          IcIcon: { template: '<span />' },
        },
      },
    })

    await wrapper.get('.component-name-trigger').trigger('click')
    await wrapper.get('.component-name-input').setValue('新按钮')
    await wrapper.get('.component-name-input').trigger('keydown.enter')

    expect(wrapper.emitted('rename')).toEqual([[item, '新按钮']])
    expect(wrapper.emitted('open')).toBeUndefined()
  })

  it('keeps the shared inline name input free of decorative underlines', () => {
    expect(componentNameEditorSource).toMatch(
      /\.component-name-input\s*\{[^}]*border:\s*0;[^}]*outline:\s*0;[^}]*box-shadow:\s*none;/su,
    )
  })

  it('renders a drawing script as a text cover with tag and language capsules without mounting a preview', () => {
    const wrapper = mount(ComponentLibraryCard, {
      props: { item: drawingScriptItem },
      global: {
        stubs: {
          ComponentPreview: { name: 'ComponentPreview', template: '<div class="preview-stub" />' },
          IcIcon: { template: '<span />' },
        },
      },
    })

    expect(wrapper.findComponent({ name: 'ComponentPreview' }).exists()).toBe(false)
    expect(wrapper.get('.drawing-title-cover').text()).toBe('销售曲线')
    expect(wrapper.findAll('.component-capsules span').map((pill) => pill.text())).toEqual([
      '绘图脚本',
      'Python',
    ])
  })

  it('uses the persisted drawing image instead of the text cover when one was uploaded', () => {
    const wrapper = mount(ComponentLibraryCard, {
      props: {
        item: {
          ...drawingScriptItem,
          cover_asset_id: 'asset-1',
          cover_asset: { asset_id: 'asset-1', url: '/cover.png' },
        } as ComponentLibraryItem,
      },
      global: { stubs: { IcIcon: { template: '<span />' } } },
    })

    expect(wrapper.get('.drawing-cover-image').attributes('src')).toBe('/cover.png')
    expect(wrapper.find('.drawing-title-cover').exists()).toBe(false)
  })
})
