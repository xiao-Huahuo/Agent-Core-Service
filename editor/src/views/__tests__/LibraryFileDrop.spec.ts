/**
 * 图书馆页面外部文件拖放测试。
 *
 * 使用说明：模拟把一个真实图片拖入页面，验证其复用知识文件上传与正式图书创建 API。
 */

import { flushPromises, shallowMount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import LibraryView from '@/views/LibraryView.vue'

const apiMocks = vi.hoisted(() => ({
  createLibraryBook: vi.fn(),
  listLibraryItems: vi.fn(),
  listLibraryTags: vi.fn(),
  uploadKnowledgeFile: vi.fn(),
}))

vi.mock('@/api/library', () => ({
  createLibraryBook: apiMocks.createLibraryBook,
  createLibraryCollection: vi.fn(),
  deleteLibraryItem: vi.fn(),
  listLibraryItems: apiMocks.listLibraryItems,
  listLibraryTags: apiMocks.listLibraryTags,
  updateLibraryItem: vi.fn(),
}))
vi.mock('@/api/knowledge', () => ({
  uploadKnowledgeFile: apiMocks.uploadKnowledgeFile,
  writeKnowledgeFile: vi.fn(),
}))
vi.mock('@/stores/settings', () => ({
  useSettingsStore: () => ({
    profile: { userId: 'u1', knowledgeDir: 'D:/Knowledge' },
    activeKnowledgeLibrary: { libraryStorageDir: '.mw/library' },
  }),
}))
vi.mock('@/stores/workspace', () => ({
  useWorkspaceStore: () => ({ loadKnowledgeTree: vi.fn(), showToast: vi.fn() }),
}))
vi.mock('@/stores/favorites', () => ({
  useFavoritesStore: () => ({ load: vi.fn(), activeLibraryId: () => 'library-1', hasLoaded: () => true, idsFor: () => new Set() }),
}))
vi.mock('@/stores/privacy', () => ({
  usePrivacyStore: () => ({ load: vi.fn(), activeLibraryId: () => 'library-1', hasLoaded: () => true, idsFor: () => new Set() }),
}))

describe('LibraryView external file drop', () => {
  it('uploads one dropped image and creates a source-image book automatically', async () => {
    apiMocks.listLibraryItems.mockResolvedValue({ items: [], parent: null, breadcrumbs: [] })
    apiMocks.listLibraryTags.mockResolvedValue({ tags: [] })
    apiMocks.uploadKnowledgeFile.mockResolvedValue({ uploaded_path: 'D:/Knowledge/.mw/library/photo.png', knowledge_dir: 'D:/Knowledge' })
    apiMocks.createLibraryBook.mockResolvedValue({ item: {} })
    const wrapper = shallowMount(LibraryView)
    const file = new File(['image'], 'photo.png', { type: 'image/png' })
    await flushPromises()

    await wrapper.get('.library-view').trigger('dragenter', { dataTransfer: { files: [file], types: ['Files'] } })
    expect(wrapper.find('.library-file-drop-overlay').exists()).toBe(true)
    await wrapper.get('.library-view').trigger('drop', { dataTransfer: { files: [file], types: ['Files'] } })
    await flushPromises()

    expect(apiMocks.uploadKnowledgeFile).toHaveBeenCalledWith('u1', file, '.mw/library', false, 'rename')
    expect(apiMocks.createLibraryBook).toHaveBeenCalledWith(expect.objectContaining({
      user_id: 'u1',
      content_type: 'knowledge_file',
      source_path: '.mw/library/photo.png',
      cover_mode: 'source_image',
      cover_asset_id: '',
    }))
  })
})
