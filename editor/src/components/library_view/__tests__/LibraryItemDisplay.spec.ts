/** 图书馆两种展示模式的真实文件下载入口测试。 */

import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import LibraryBar from '@/components/library_view/LibraryBar.vue'
import LibraryCard from '@/components/library_view/LibraryCard.vue'
import type { LibraryItem } from '@/types/knowledge'

const book = {
  item_id: 'book-1', user_id: 'u1', library_id: 'l1', parent_id: '', item_type: 'book', content_type: 'knowledge_file',
  title: '脚本', display_title: '脚本', description: '', storage_path: '.mw/library/demo.py', source_path: '.mw/library/demo.py',
  source_url: '', source_name: 'demo.py', source_mime: 'text/x-python', source_size: 1, source_mtime: '', source_exists: true,
  cover_mode: 'icon', cover_asset_id: '', cover_asset: null, sort_order: 0, index_status: '', graph_status: '', tags: [], child_count: 0,
  created_at: '', updated_at: '',
} as LibraryItem

const options = {
  props: { item: book, selected: false, multiSelect: false },
  global: { stubs: { IcIcon: { template: '<span />' }, FavoriteButton: { template: '<span />' } } },
}

describe('Library item download affordances', () => {
  it('places the card download control next to the title and emits the real book', async () => {
    const wrapper = mount(LibraryCard, options)
    await wrapper.get('button[aria-label="下载真实文件"]').trigger('click')
    expect(wrapper.emitted('download')?.[0]).toEqual([book])
  })

  it('places the bar download control in the right-side footer and emits the real book', async () => {
    const wrapper = mount(LibraryBar, options)
    await wrapper.get('.bar-foot button[aria-label="下载真实文件"]').trigger('click')
    expect(wrapper.emitted('download')?.[0]).toEqual([book])
  })

  it('closes the card detail popover when the card loses its selected state', async () => {
    const wrapper = mount(LibraryCard, options)
    await wrapper.get('.expand-button').trigger('click')
    expect(wrapper.find('.details-popover').exists()).toBe(true)
    await wrapper.setProps({ selected: true })
    await wrapper.setProps({ selected: false })
    expect(wrapper.find('.details-popover').exists()).toBe(false)
  })

  it('edits title and description inline then emits each automatic save', async () => {
    const wrapper = mount(LibraryCard, options)
    await wrapper.get('.title').trigger('dblclick')
    await wrapper.get('input[aria-label="编辑图书名"]').setValue('新标题')
    await wrapper.get('input[aria-label="编辑图书名"]').trigger('keydown', { key: 'Enter' })
    expect(wrapper.emitted('save')?.[0]).toEqual([book, { title: '新标题' }])

    await wrapper.get('.expand-button').trigger('click')
    await wrapper.get('.description').trigger('dblclick')
    await wrapper.get('textarea[aria-label="编辑描述"]').setValue('新描述')
    await wrapper.get('textarea[aria-label="编辑描述"]').trigger('blur')
    expect(wrapper.emitted('save')?.[1]).toEqual([book, { description: '新描述' }])
  })
})
