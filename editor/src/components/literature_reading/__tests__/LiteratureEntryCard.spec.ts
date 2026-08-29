/** Literature search-card expansion policy tests. */

import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import LiteratureEntryCard from '@/components/literature_reading/LiteratureEntryCard.vue'

const entry = {
  form_id: 'form-1', form_title: '文献', row_id: 'row-1', title: '论文', file_name: 'paper.pdf',
  asset_path: 'paper.pdf', content_excerpt: '摘要', file_size: 10, entered_at: '2026-08-29T00:00:00',
  updated_at: '2026-08-29T00:00:00', last_viewed_at: '', tags: [], rating: 0,
}

describe('LiteratureEntryCard expansion policy', () => {
  it('removes all expansion affordances when used as a search result block', async () => {
    const wrapper = mount(LiteratureEntryCard, {
      props: {
        entry, form: null, row: null, selected: false, renaming: false,
        pendingColumnIds: [], expandable: false,
      },
      global: {
        stubs: {
          RecentFileThumbnail: true,
          FormHeightTransition: { template: '<div><slot /></div>' },
          IcIcon: true,
        },
      },
    })

    expect(wrapper.find('.expand-button').exists()).toBe(false)
    expect(wrapper.find('.field-list').exists()).toBe(false)
    await wrapper.get('.literature-card').trigger('click')
    expect(wrapper.emitted('select')).toHaveLength(1)
  })
})
