/*
 * Password vault table icon tests.
 *
 * Usage:
 * Verifies the unlabeled icon column, local SVG type-icon fallback, and
 * uploaded-image precedence without depending on protected asset requests.
 */
import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import type { VaultItem } from '@/api/vault'
import VaultTable from '@/components/vault_view/VaultTable.vue'
import tableSource from '@/components/vault_view/VaultTable.vue?raw'

vi.mock('@/components/common/IcIcon.vue', () => ({
  default: {
    props: ['name'],
    template: '<i class="mock-icon" :data-icon="name"></i>',
  },
}))

vi.mock('@/components/vault_view/VaultAssetThumb.vue', () => ({
  default: {
    props: ['assetId', 'fallbackIcon'],
    template: '<i class="mock-asset" :data-asset="assetId" :data-fallback="fallbackIcon"></i>',
  },
}))

function vaultItem(itemType: VaultItem['item_type'], assetIds: string[] = []): VaultItem {
  return {
    item_id: `${itemType}-id`,
    item_type: itemType,
    name: itemType,
    user_id: 'user-1',
    created_at: '2026-08-14T00:00:00Z',
    updated_at: '2026-08-14T00:00:00Z',
    fields: { asset_ids: assetIds },
    tags: [],
  } as VaultItem
}

describe('VaultTable icons', () => {
  it('keeps the icon column header visually empty', () => {
    const wrapper = mount(VaultTable, { props: { token: 'token', items: [], selectedIds: new Set(), multiSelect: false } })

    expect(wrapper.findAll('th')[0]?.text()).toBe('')
    expect(tableSource).not.toContain('<th>图标</th>')
  })

  it('uses local SVG icons instead of emoji for every vault type', () => {
    const wrapper = mount(VaultTable, {
      props: {
        token: 'token',
        items: [vaultItem('login'), vaultItem('card'), vaultItem('identity'), vaultItem('secure_note')],
        selectedIds: new Set(),
        multiSelect: false,
      },
    })

    expect(wrapper.findAll('.mock-icon').map((icon) => icon.attributes('data-icon'))).toEqual([
      'shield',
      'dashboard',
      'fact-check',
      'edit-note',
    ])
    expect(tableSource).not.toMatch(/[💳🔑]/u)
  })

  it('renders an uploaded image first and keeps the SVG icon as its failure fallback', () => {
    const wrapper = mount(VaultTable, {
      props: {
        token: 'token',
        items: [vaultItem('card', ['asset-1'])],
        selectedIds: new Set(),
        multiSelect: false,
      },
    })

    expect(wrapper.get('.mock-asset').attributes()).toMatchObject({
      'data-asset': 'asset-1',
      'data-fallback': 'dashboard',
    })
    expect(wrapper.find('.mock-icon').exists()).toBe(false)
  })
})
