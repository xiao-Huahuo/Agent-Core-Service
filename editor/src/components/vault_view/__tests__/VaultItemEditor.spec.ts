/*
 * Password vault item editor image-preview tests.
 *
 * Usage:
 * Verifies that a successful protected asset upload replaces the upload prompt
 * with the same full-cover presentation used by the library creation form.
 */
import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import VaultItemEditor from '@/components/vault_view/VaultItemEditor.vue'

const { uploadVaultAsset } = vi.hoisted(() => ({ uploadVaultAsset: vi.fn() }))

vi.mock('@/api/vault', async (importOriginal) => {
  const original = await importOriginal<typeof import('@/api/vault')>()
  return { ...original, uploadVaultAsset }
})

vi.mock('@/components/common/IcIcon.vue', () => ({
  default: { props: ['name'], template: '<i :data-icon="name"></i>' },
}))

vi.mock('@/components/vault_view/VaultAssetThumb.vue', () => ({
  default: {
    props: ['assetId', 'display'],
    template: '<img class="mock-preview" :data-asset="assetId" :data-display="display" />',
  },
}))

describe('VaultItemEditor image upload', () => {
  it('shows the uploaded image as a full cover preview', async () => {
    uploadVaultAsset.mockResolvedValueOnce({ asset: { asset_id: 'asset-1' } })
    const wrapper = mount(VaultItemEditor, {
      props: { open: true, item: null, token: 'vault-token', availableTags: [] },
      global: { stubs: { Teleport: true } },
    })
    const input = wrapper.get('input[type="file"]')
    Object.defineProperty(input.element, 'files', { value: [new File(['image'], 'cover.png', { type: 'image/png' })] })

    await input.trigger('change')
    await flushPromises()

    expect(wrapper.get('.mock-preview').attributes()).toMatchObject({
      'data-asset': 'asset-1',
      'data-display': 'cover',
    })
    expect(wrapper.text()).not.toContain('点击上传图片')
  })
})
