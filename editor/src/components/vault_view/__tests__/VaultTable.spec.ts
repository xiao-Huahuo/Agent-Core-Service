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
    safe_fields: { asset_ids: assetIds },
    tags: [],
    deleted_at: '',
  }
}

function vaultItemWithFields(itemType: VaultItem['item_type'], id: string, fields: Record<string, unknown>): VaultItem {
  return {
    ...vaultItem(itemType),
    item_id: id,
    name: String(fields.name ?? id),
    fields,
  }
}

describe('VaultTable icons', () => {
  it('keeps the icon column header visually empty', () => {
    const wrapper = mount(VaultTable, { props: { token: 'token', items: [], selectedIds: new Set<string>(), multiSelect: false } })

    expect(wrapper.findAll('th')[0]?.text()).toBe('')
    expect(tableSource).not.toContain('<th>图标</th>')
  })

  it('uses local SVG icons instead of emoji for every vault type', () => {
    const wrapper = mount(VaultTable, {
      props: {
        token: 'token',
        items: [vaultItem('login'), vaultItem('card'), vaultItem('identity'), vaultItem('secure_note')],
        selectedIds: new Set<string>(),
        multiSelect: false,
      },
    })

    expect(wrapper.findAll('.type-icon .mock-icon').map((icon) => icon.attributes('data-icon'))).toEqual([
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
        selectedIds: new Set<string>(),
        multiSelect: false,
      },
    })

    expect(wrapper.get('.mock-asset').attributes()).toMatchObject({
      'data-asset': 'asset-1',
      'data-fallback': 'dashboard',
    })
    expect(wrapper.find('.type-icon .mock-icon').exists()).toBe(false)
  })

  it('uses the union of non-empty fields for the selected password type', () => {
    const wrapper = mount(VaultTable, {
      props: {
        token: 'token',
        items: [
          vaultItemWithFields('login', 'login-1', { name: '工作账号', username: 'alice', password: 'secret', uri: '' }),
          vaultItemWithFields('login', 'login-2', { name: '私人账号', username: '', password: 'secret-2', uri: 'https://example.com' }),
        ],
        itemType: 'login',
        selectedIds: new Set<string>(),
        multiSelect: false,
      },
    })

    expect(wrapper.findAll('th').map((cell) => cell.text())).toEqual([
      '', '项目名称', '用户名', '密码', '网站 URI', '创建时间', '拥有者',
    ])
    expect(wrapper.text()).not.toContain('secret')
  })

  it('changes the dynamic column count when the selected password type changes', async () => {
    const wrapper = mount(VaultTable, {
      props: {
        token: 'token',
        items: [vaultItemWithFields('card', 'card-1', { name: '主卡', number: '6222', brand: 'UnionPay银联' })],
        itemType: 'card',
        selectedIds: new Set<string>(),
        multiSelect: false,
      },
    })
    expect(wrapper.findAll('th').map((cell) => cell.text())).toEqual([
      '', '项目名称', '卡号', '品牌', '创建时间', '拥有者',
    ])

    await wrapper.setProps({
      itemType: 'secure_note',
      items: [vaultItemWithFields('secure_note', 'note-1', { name: '备忘', note: '只有一列' })],
    })
    expect(wrapper.findAll('th').map((cell) => cell.text())).toEqual([
      '', '项目名称', '笔记内容', '创建时间', '拥有者',
    ])
  })
})
