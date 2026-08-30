/** Library handoff tests for search blocks clicked from the sidebar Agent. */
import { flushPromises, shallowMount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useFavoritesStore } from '@/stores/favorites'
import { usePrivacyStore } from '@/stores/privacy'
import { useSettingsStore } from '@/stores/settings'
import { useWorkspaceStore } from '@/stores/workspace'
import type { LibraryItem } from '@/types/knowledge'
import LibraryView from '@/views/LibraryView.vue'

const listLibraryItems = vi.fn()
const listLibraryTags = vi.fn()

vi.mock('@/api/library', () => ({
  createLibraryBook: vi.fn(),
  createLibraryCollection: vi.fn(),
  deleteLibraryItem: vi.fn(),
  listLibraryItems: (...args: unknown[]) => listLibraryItems(...args),
  listLibraryTags: (...args: unknown[]) => listLibraryTags(...args),
  updateLibraryItem: vi.fn(),
}))

describe('LibraryView Agent search-result handoff', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    useSettingsStore().profile.userId = 'u1'
    listLibraryTags.mockReset().mockResolvedValue({ tags: [] })
  })

  it('opens the exact book and its detail drawer after the main-page switch', async () => {
    const item: LibraryItem = {
      item_id: 'book-1', user_id: 'u1', library_id: 'lib-1', parent_id: 'collection-1',
      item_type: 'book', content_type: 'knowledge_file', title: 'Agent Book', display_title: 'Agent Book',
      description: '', storage_path: '', source_path: 'docs/book.pdf', source_url: '', source_name: 'book.pdf',
      source_mime: 'application/pdf', source_size: 12, source_mtime: '', source_exists: true, cover_mode: 'title',
      cover_asset_id: '', cover_asset: null, sort_order: 0, index_status: '', graph_status: '', tags: [], child_count: 0,
      created_at: '', updated_at: '',
    }
    listLibraryItems.mockReset().mockResolvedValue({ items: [item], parent: null, breadcrumbs: [] })
    const workspaceStore = useWorkspaceStore()
    vi.spyOn(workspaceStore, 'loadKnowledgeTree').mockResolvedValue(undefined)
    vi.spyOn(useFavoritesStore(), 'load').mockResolvedValue(undefined)
    vi.spyOn(usePrivacyStore(), 'load').mockResolvedValue(undefined)
    workspaceStore.pendingMainSearchResult = {
      id: item.item_id, source: 'library', title: item.display_title, snippet: '', locator: item.source_path,
      updated_at: '', score: 1, matched_modes: ['title'], item: { ...item },
    }

    const wrapper = shallowMount(LibraryView)
    await flushPromises()

    expect(wrapper.get('.drawer-title').text()).toBe('Agent Book')
    expect(listLibraryItems).toHaveBeenCalledWith(expect.objectContaining({ parentId: 'collection-1' }))
    expect(workspaceStore.pendingMainSearchResult).toBeNull()
  })
})
