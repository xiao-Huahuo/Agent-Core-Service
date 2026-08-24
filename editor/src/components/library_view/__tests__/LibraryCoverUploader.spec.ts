/*
 * Shared library cover uploader tests.
 *
 * Usage:
 * Verifies the extracted uploader owns the existing cover API interaction and
 * is reused by both library forms and appearance settings.
 */

import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import LibraryCoverUploader from '@/components/library_view/LibraryCoverUploader.vue'
import createDialogSource from '@/components/library_view/LibraryCreateDialog.vue?raw'
import itemDialogSource from '@/components/library_view/LibraryItemDialog.vue?raw'
import appearanceSource from '@/components/settings_view/AppearanceSettingsSection.vue?raw'

const apiMocks = vi.hoisted(() => ({ uploadLibraryCover: vi.fn() }))

vi.mock('@/api/library', () => ({ uploadLibraryCover: apiMocks.uploadLibraryCover }))

describe('LibraryCoverUploader', () => {
  it('uploads one selected image and emits its persistent asset', async () => {
    const asset = {
      asset_id: 'asset-1', mime_type: 'image/png', file_name: 'cover.png',
      url: '/library/assets/u1/asset-1.png', width: 1200, height: 800, size: 12, created_at: '',
    }
    apiMocks.uploadLibraryCover.mockResolvedValueOnce({ asset })
    const wrapper = mount(LibraryCoverUploader, { props: { userId: 'u1', previewUrl: '' } })
    const file = new File(['cover'], 'cover.png', { type: 'image/png' })
    const input = wrapper.get('input[type="file"]')
    Object.defineProperty(input.element, 'files', { configurable: true, value: [file] })

    await input.trigger('change')

    expect(apiMocks.uploadLibraryCover).toHaveBeenCalledWith('u1', file)
    expect(wrapper.emitted('uploaded')?.[0]?.[0]).toEqual(asset)
  })

  it('is reused by both library forms and appearance settings', () => {
    expect(createDialogSource).toContain('<LibraryCoverUploader')
    expect(itemDialogSource).toContain('<LibraryCoverUploader')
    expect(appearanceSource).toContain('<LibraryCoverUploader')
  })
})
