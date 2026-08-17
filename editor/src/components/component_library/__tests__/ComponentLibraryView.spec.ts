/** Component library page and upload-form acceptance tests. */

import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import CompactCodeInput from '@/components/common/CompactCodeInput.vue'
import ComponentUploadForm from '@/components/component_library/ComponentUploadForm.vue'
import { useSettingsStore } from '@/stores/settings'
import { COMPONENT_TAGS } from '@/types/componentLibrary'
import ComponentLibraryView from '@/views/ComponentLibraryView.vue'

const listComponentLibraryItems = vi.fn()
const createComponentLibraryItem = vi.fn()
const renameComponentLibraryItem = vi.fn()
const deleteKnowledgePath = vi.fn()

vi.mock('@/api/componentLibrary', () => ({
  listComponentLibraryItems: (...args: unknown[]) => listComponentLibraryItems(...args),
  createComponentLibraryItem: (...args: unknown[]) => createComponentLibraryItem(...args),
  renameComponentLibraryItem: (...args: unknown[]) => renameComponentLibraryItem(...args),
}))

vi.mock('@/api/knowledge', () => ({
  deleteKnowledgePath: (...args: unknown[]) => deleteKnowledgePath(...args),
}))

vi.mock('@/components/common/IcIcon.vue', () => ({
  default: { template: '<span class="icon" />' },
}))

describe('ComponentLibraryView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    useSettingsStore().profile.userId = 'u1'
    listComponentLibraryItems.mockReset()
    createComponentLibraryItem.mockReset()
    renameComponentLibraryItem.mockReset()
    deleteKnowledgePath.mockReset()
    deleteKnowledgePath.mockResolvedValue({ ok: true, trash_id: 'trash-1' })
    listComponentLibraryItems.mockResolvedValue({
      tags: [...COMPONENT_TAGS],
      components: [{
        component_id: 'buttons/button.vue',
        user_id: 'u1',
        title: '按钮',
        tag: 'buttons',
        source_format: 'vue',
        source: '<template><button>OK</button></template>',
        builtin: true,
        created_at: null,
        updated_at: null,
      }],
    })
    renameComponentLibraryItem.mockResolvedValue({
      component: {
        component_id: 'buttons/新按钮.vue',
        user_id: 'u1',
        title: '新按钮',
        tag: 'buttons',
        source_format: 'vue',
        source: '<template><button>OK</button></template>',
        builtin: false,
        created_at: null,
        updated_at: null,
      },
    })
  })

  it('renders All first, keeps upload in the internal toolbar, and shows real component blocks', async () => {
    const wrapper = mount(ComponentLibraryView, {
      global: {
        stubs: {
          ComponentLibraryCard: { props: ['item'], template: '<article class="card-stub">{{ item.tag }}</article>' },
        },
      },
    })
    await flushPromises()

    expect(wrapper.findAll('.tag-option').map((item) => item.text())).toEqual([
      'all',
      ...COMPONENT_TAGS.filter((tag) => tag !== 'any'),
    ])
    expect(wrapper.find('.card-stub').text()).toBe('buttons')
    expect(listComponentLibraryItems).toHaveBeenCalledWith('u1', 'any')
    expect(wrapper.find('.tag-sidebar .upload-trigger').exists()).toBe(false)
    expect(wrapper.get('.component-toolbar .upload-trigger').text()).toContain('上传组件')
    expect(wrapper.find('.toolbar-copy span').exists()).toBe(false)

    await wrapper.findAll('.tag-option')[2]?.trigger('click')
    await flushPromises()
    expect(listComponentLibraryItems).toHaveBeenLastCalledWith('u1', 'checkboxes')
  })

  it('filters the current component grid from the sidebar search field', async () => {
    listComponentLibraryItems.mockResolvedValueOnce({
      tags: [...COMPONENT_TAGS],
      components: [
        {
          component_id: 'buttons/primary.vue',
          user_id: 'u1',
          title: 'Primary Button',
          tag: 'buttons',
          source_format: 'vue',
          source: '<template><button>Primary</button></template>',
          builtin: false,
          created_at: null,
          updated_at: null,
        },
        {
          component_id: 'cards/profile.vue',
          user_id: 'u1',
          title: 'Profile Card',
          tag: 'cards',
          source_format: 'vue',
          source: '<template><article>Profile</article></template>',
          builtin: false,
          created_at: null,
          updated_at: null,
        },
      ],
    })
    const wrapper = mount(ComponentLibraryView, {
      global: {
        stubs: {
          ComponentLibraryCard: { props: ['item'], template: '<article class="card-stub">{{ item.title }}</article>' },
        },
      },
    })
    await flushPromises()

    const search = wrapper.get('.tag-sidebar input[type="search"]')
    expect(search.attributes('placeholder')).toBe('搜索组件')
    await search.setValue('profile')

    expect(wrapper.findAll('.card-stub').map((card) => card.text())).toEqual(['Profile Card'])
  })

  it('opens a dedicated preview-and-source detail page from a card event', async () => {
    const wrapper = mount(ComponentLibraryView, {
      global: {
        stubs: {
          ComponentLibraryCard: {
            props: ['item'],
            template: '<button class="open-card" @click="$emit(\'open\', item)">{{ item.title }}</button>',
          },
          ComponentLibraryDetail: {
            props: ['item'],
            template: '<section class="detail-stub">{{ item.source }}</section>',
          },
        },
      },
    })
    await flushPromises()

    await wrapper.get('.open-card').trigger('click')
    expect(wrapper.get('.detail-stub').text()).toContain('<template>')
    expect(wrapper.get('.component-toolbar').text()).toContain('按钮')
    expect(wrapper.get('.component-content').classes()).toContain('detail-content')
    expect(wrapper.find('.component-grid').exists()).toBe(false)

    await wrapper.get('.detail-back').trigger('click')
    expect(wrapper.find('.detail-stub').exists()).toBe(false)
    expect(wrapper.find('.component-grid').exists()).toBe(true)
  })

  it('persists card renames and replaces the visible component item', async () => {
    const wrapper = mount(ComponentLibraryView, {
      global: {
        stubs: {
          ComponentLibraryCard: {
            props: ['item'],
            template: '<button class="rename-card" @click="$emit(\'rename\', item, \'新按钮\')">{{ item.title }}</button>',
          },
        },
      },
    })
    await flushPromises()

    await wrapper.get('.rename-card').trigger('click')
    await flushPromises()

    expect(renameComponentLibraryItem).toHaveBeenCalledWith('u1', 'buttons/button.vue', '新按钮')
    expect(wrapper.get('.rename-card').text()).toBe('新按钮')
  })

  it('places code left, live preview right, and the single tag selector below', () => {
    const wrapper = mount(ComponentUploadForm, {
      props: { userId: 'u1' },
      global: {
        stubs: {
          Teleport: true,
          ComponentPreview: { template: '<div class="preview-stub" />' },
          LibraryTagPicker: {
            name: 'LibraryTagPicker',
            props: ['single', 'allowCustom', 'dropdownAlignOffset'],
            template: '<div class="tag-picker-stub" />',
          },
        },
      },
    })

    const compilerChildren = wrapper.get('.compiler-grid').element.children
    expect(compilerChildren[0]?.classList.contains('code-panel')).toBe(true)
    expect(compilerChildren[1]?.classList.contains('preview-panel')).toBe(true)
    expect(wrapper.get('.tag-field').element.compareDocumentPosition(wrapper.get('.compiler-grid').element)).toBe(
      Node.DOCUMENT_POSITION_PRECEDING,
    )
    expect(wrapper.get('.name-field').element.compareDocumentPosition(wrapper.get('.tag-field').element)).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    )
    expect(wrapper.get('input[name="component-name"]').attributes('maxlength')).toBe('180')
    expect(wrapper.get('input[name="component-name"]').attributes('placeholder')).toBeUndefined()
    expect(wrapper.getComponent({ name: 'LibraryTagPicker' }).props()).toMatchObject({
      single: true,
      allowCustom: false,
      dropdownAlignOffset: 24,
    })
    expect(wrapper.find('.upload-backdrop').exists()).toBe(true)
    expect(wrapper.get('.upload-form').attributes('aria-modal')).toBe('true')
    expect(wrapper.find('.form-header p').exists()).toBe(false)
    expect(wrapper.get('.preview-placeholder').text()).toBe('')
    expect(wrapper.get('.file-picker-button').text()).toBe('')
    expect(wrapper.findComponent(CompactCodeInput).exists()).toBe(true)
  })

  it('confirms and moves a card component to the knowledge trash', async () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)
    const wrapper = mount(ComponentLibraryView, {
      global: {
        stubs: {
          ComponentLibraryCard: {
            props: ['item'],
            template: '<button class="delete-card" @click="$emit(\'delete\', item)">{{ item.title }}</button>',
          },
        },
      },
    })
    await flushPromises()

    await wrapper.get('.delete-card').trigger('click')
    await flushPromises()

    expect(confirm).toHaveBeenCalledOnce()
    expect(deleteKnowledgePath).toHaveBeenCalledWith('u1', 'components/buttons/button.vue')
    expect(wrapper.find('.delete-card').exists()).toBe(false)
  })

  it('keeps the component grid mounted behind the centered upload dialog', async () => {
    const wrapper = mount(ComponentLibraryView, {
      global: {
        stubs: {
          Teleport: true,
          ComponentLibraryCard: { props: ['item'], template: '<article class="card-stub">{{ item.tag }}</article>' },
          ComponentUploadForm: { template: '<section class="upload-dialog-stub" />' },
        },
      },
    })
    await flushPromises()

    await wrapper.get('.upload-trigger').trigger('click')
    expect(wrapper.find('.upload-dialog-stub').exists()).toBe(true)
    expect(wrapper.find('.component-grid').exists()).toBe(true)
  })

  it('submits the compiled code and one selected tag to the real API client boundary', async () => {
    createComponentLibraryItem.mockResolvedValue({
      component: {
        component_id: 'uploaded-1',
        user_id: 'u1',
        title: '组件 uploaded',
        tag: 'buttons',
        source_format: 'vue',
        source: '<template><button>OK</button></template>',
        builtin: false,
        created_at: '2026-08-16T00:00:00Z',
        updated_at: '2026-08-16T00:00:00Z',
      },
    })
    const wrapper = mount(ComponentUploadForm, {
      props: { userId: 'u1' },
      global: {
        stubs: {
          Teleport: true,
          ComponentPreview: { template: '<div />' },
          LibraryTagPicker: {
            template: '<button class="choose-tag" @click="$emit(\'update:modelValue\', [\'buttons\'])">buttons</button>',
          },
          IcIcon: { template: '<span />' },
        },
      },
    })
    const source = '<template><button>OK</button></template>'
    await wrapper.get('input[name="component-name"]').setValue('确认按钮')
    await wrapper.get('textarea').setValue(source)
    await wrapper.get('.choose-tag').trigger('click')
    await wrapper.get('.primary-button').trigger('click')
    await flushPromises()

    expect(createComponentLibraryItem).toHaveBeenCalledWith({
      user_id: 'u1',
      source,
      tag: 'buttons',
      filename: '确认按钮.vue',
    })
    expect(wrapper.emitted('created')).toHaveLength(1)
  })

  it('accepts one or many Vue/HTML files and persists every selected file', async () => {
    createComponentLibraryItem
      .mockResolvedValueOnce({ component: { component_id: 'one.vue' } })
      .mockResolvedValueOnce({ component: { component_id: 'two.html' } })
    const wrapper = mount(ComponentUploadForm, {
      props: { userId: 'u1' },
      global: {
        stubs: {
          Teleport: true,
          ComponentPreview: { template: '<div />' },
          LibraryTagPicker: {
            template: '<button class="choose-tag" @click="$emit(\'update:modelValue\', [\'buttons\'])">buttons</button>',
          },
          IcIcon: { template: '<span />' },
        },
      },
    })
    const input = wrapper.get('input[type="file"]')
    const files = [
      new File(['<template><button>One</button></template>'], 'one.vue', { type: 'text/plain' }),
      new File(['<button>Two</button>'], 'two.html', { type: 'text/html' }),
    ]
    Object.defineProperty(input.element, 'files', { value: files, configurable: true })
    await input.trigger('change')
    await flushPromises()
    expect(wrapper.get('input[name="component-name"]').element).toHaveProperty('value', 'one')
    await wrapper.get('.choose-tag').trigger('click')
    await wrapper.get('.primary-button').trigger('click')
    await flushPromises()

    expect(input.attributes('multiple')).toBeDefined()
    expect(input.attributes('accept')).toBe('.vue,.html,.htm,text/html')
    expect(createComponentLibraryItem).toHaveBeenNthCalledWith(1, {
      user_id: 'u1',
      source: '<template><button>One</button></template>',
      tag: 'buttons',
      filename: 'one.vue',
    })
    expect(createComponentLibraryItem).toHaveBeenNthCalledWith(2, {
      user_id: 'u1',
      source: '<button>Two</button>',
      tag: 'buttons',
      filename: 'two.html',
    })
  })
})
