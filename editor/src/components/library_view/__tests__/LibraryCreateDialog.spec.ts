/** 新增图书表单的来源模式与提交契约测试。 */

import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import CompactCodeInput from '@/components/common/CompactCodeInput.vue'
import LibraryCreateDialog from '@/components/library_view/LibraryCreateDialog.vue'

vi.mock('@/api/library', () => ({
  uploadLibraryCover: vi.fn(),
}))

describe('LibraryCreateDialog', () => {
  /** 挂载打开状态的新增图书表单，并隔离与本验收无关的标签选择器。 */
  function mountDialog() {
    return mount(LibraryCreateDialog, {
      props: {
        open: true,
        mode: 'book',
        userId: 'u1',
        availableTags: [],
      },
      global: {
        stubs: {
          Teleport: true,
          LibraryTagPicker: { template: '<div />' },
          IcIcon: { template: '<span />' },
        },
      },
    })
  }

  it('adds the script action at the lower-left and switches the body to the shared compact code input', async () => {
    const wrapper = mountDialog()

    const scriptButton = wrapper.get('.source-mode-actions button[aria-label="脚本"]')
    expect(scriptButton.attributes('aria-label')).toBe('脚本')
    await scriptButton.trigger('click')

    expect(wrapper.get('.source-mode-actions button[aria-label="脚本"]').classes()).toContain('active')
    expect(wrapper.findComponent(CompactCodeInput).exists()).toBe(true)
    expect(wrapper.find('.text-content-field').exists()).toBe(false)
  })

  it('places the cover upload zone before metadata for both books and collections', () => {
    for (const mode of ['book', 'collection'] as const) {
      const wrapper = mount(LibraryCreateDialog, {
        props: { open: true, mode, userId: 'u1', availableTags: [] },
        global: { stubs: { Teleport: true, LibraryTagPicker: { template: '<div />' }, IcIcon: { template: '<span />' } } },
      })
      const zones = wrapper.get('.upper-grid').element.children
      expect(zones[0]?.classList.contains('cover-zone')).toBe(true)
      expect(zones[1]?.classList.contains('metadata-zone')).toBe(true)
    }
  })

  it('right-aligns the collection cancel and create actions', () => {
    const wrapper = mount(LibraryCreateDialog, {
      props: { open: true, mode: 'collection', userId: 'u1', availableTags: [] },
      global: { stubs: { Teleport: true, LibraryTagPicker: { template: '<div />' }, IcIcon: { template: '<span />' } } },
    })
    expect(wrapper.get('.dialog-actions').classes()).toContain('collection-actions')
    expect(wrapper.find('.source-mode-actions').exists()).toBe(false)
  })

  it('submits script content with its requested real-file extension', async () => {
    const wrapper = mountDialog()
    await wrapper.get('.source-mode-actions button[aria-label="脚本"]').trigger('click')
    await wrapper.getComponent(CompactCodeInput).get('textarea').setValue('print("MetaWeave")')
    await wrapper.get('input[aria-label="代码文件后缀"]').setValue('.r')
    await wrapper.get('.primary-btn').trigger('click')

    expect(wrapper.emitted('create')?.[0]?.[0]).toMatchObject({
      source_mode: 'script',
      text_content: 'print("MetaWeave")',
      script_extension: '.r',
      file: null,
      source_url: '',
    })
  })
})
