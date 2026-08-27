/**
 * 图书编辑表单封面模式测试。
 *
 * 使用说明：验证真实图片图书与普通文件图书只出现各自适用的一种图片封面模式。
 */

import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import LibraryItemDialog from '@/components/library_view/LibraryItemDialog.vue'
import type { LibraryItem } from '@/types/knowledge'

vi.mock('@/api/library', () => ({ uploadLibraryCover: vi.fn() }))

/** Reusable ordinary-file book fixture overridden only by each cover-mode scenario. */
const baseItem: LibraryItem = {
  item_id: 'book-1', user_id: 'u1', library_id: 'library-1', parent_id: '', item_type: 'book',
  content_type: 'knowledge_file', title: '图书', display_title: '图书', description: '',
  storage_path: '.mw/library/book.txt', source_path: '.mw/library/book.txt', source_url: '',
  source_name: 'book.txt', source_mime: 'text/plain', source_size: 1, source_mtime: '', source_exists: true,
  cover_mode: 'icon', cover_asset_id: '', cover_asset: null, sort_order: 0, index_status: '', graph_status: '',
  tags: [], child_count: 0, created_at: '', updated_at: '',
}

/** 挂载元信息模式中的编辑表单。 */
function mountDialog(item: LibraryItem) {
  return mount(LibraryItemDialog, {
    props: { open: true, item, userId: 'u1', availableTags: [] },
    global: {
      stubs: {
        Teleport: true,
        LibraryTagPicker: { template: '<div />' },
        LibraryRealContentPanel: { template: '<div />' },
        IcIcon: { template: '<span />' },
      },
    },
  })
}

describe('LibraryItemDialog cover modes', () => {
  it('shows only source-image mode when the real file is an image', () => {
    const wrapper = mountDialog({ ...baseItem, source_path: '.mw/library/photo.jpeg', source_name: 'photo.jpeg', source_mime: '' })

    expect(wrapper.text()).toContain('使用真实图片')
    expect(wrapper.text()).not.toContain('上传图片')
  })

  it('shows only upload-image mode when the real file is not an image', () => {
    const wrapper = mountDialog(baseItem)

    expect(wrapper.text()).toContain('上传图片')
    expect(wrapper.text()).not.toContain('使用真实图片')
  })
})
