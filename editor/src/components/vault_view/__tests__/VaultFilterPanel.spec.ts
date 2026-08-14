/*
 * Password-vault filter panel tests.
 * Verifies that search input lives in the filter panel and updates its model.
 */
import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import VaultFilterPanel from '../VaultFilterPanel.vue'
import filterPanelSource from '../VaultFilterPanel.vue?raw'

vi.mock('@/components/common/IcIcon.vue', () => ({
  default: { template: '<span />' },
}))

describe('VaultFilterPanel', () => {
  it('emits the sidebar search query', async () => {
    const wrapper = mount(VaultFilterPanel, {
      props: {
        query: '',
        tag: '',
        itemType: '',
        tags: [],
        counts: {},
      },
    })

    const search = wrapper.get('input[type="search"]')
    await search.setValue('邮箱')

    expect(search.attributes('placeholder')).toBe('搜索密码库')
    expect(wrapper.emitted('update:query')).toEqual([['邮箱']])
  })

  it('constrains the search field to the sidebar track', () => {
    expect(filterPanelSource).toContain('grid-template-columns: minmax(0, 1fr)')
    expect(filterPanelSource).toContain('max-width: 216px')
    expect(filterPanelSource).toContain('.filter-search')
    expect(filterPanelSource).toContain('max-width: 100%')
  })
})
