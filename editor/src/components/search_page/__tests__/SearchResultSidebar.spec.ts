/**
 * Search result editor-sidebar integration tests.
 *
 * Usage:
 * Verifies library, component, and literature editors persist through their
 * canonical APIs, update the current result locally, and never rerun search.
 */

import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import SearchResultSidebar from '@/components/search_page/SearchResultSidebar.vue'
import { useSettingsStore } from '@/stores/settings'
import { useWorkspaceStore } from '@/stores/workspace'
import type { UnifiedSearchResult, UnifiedSearchResponse } from '@/types/unifiedSearch'

const updateLibraryItem = vi.fn()
const listLibraryTags = vi.fn()
const writeKnowledgeFile = vi.fn()
const updateComponentLibraryItem = vi.fn()
const getSmartFormDb = vi.fn()
const patchLiteratureRow = vi.fn()

vi.mock('@/api/library', () => ({
  updateLibraryItem: (...args: unknown[]) => updateLibraryItem(...args),
  listLibraryTags: (...args: unknown[]) => listLibraryTags(...args),
}))
vi.mock('@/api/knowledge', () => ({ writeKnowledgeFile: (...args: unknown[]) => writeKnowledgeFile(...args) }))
vi.mock('@/api/componentLibrary', () => ({
  updateComponentLibraryItem: (...args: unknown[]) => updateComponentLibraryItem(...args),
}))
vi.mock('@/api/smartForms', () => ({ getSmartFormDb: (...args: unknown[]) => getSmartFormDb(...args) }))
vi.mock('@/api/literatureReading', () => ({ patchLiteratureRow: (...args: unknown[]) => patchLiteratureRow(...args) }))

function response(result: UnifiedSearchResult): UnifiedSearchResponse {
  return {
    query: 'alpha', selected_sources: [result.source], fulltext: true, semantic: false,
    results: [result],
    groups: { files: [], library: [], components: [], literature: [], [result.source]: [result] },
    counts: { files: 0, library: 0, components: 0, literature: 0, [result.source]: 1 },
    total: 1,
  }
}

function mountSidebar(result: UnifiedSearchResult) {
  return mount(SearchResultSidebar, {
    props: { result },
    global: {
      stubs: {
        EditorSidebarCloseButton: { template: '<button class="close-sidebar" @click="$emit(\'close\')">close</button>' },
        LibraryItemDialog: {
          props: ['item'],
          template: '<button class="library-save" @click="$emit(\'save\', { title: \'新版图书\', description: \'说明\', cover_mode: \'title\', cover_asset_id: \'\', tags: [], source_content: \'新正文\' })">save</button>',
        },
        ComponentLibraryDetail: {
          props: ['item'],
          template: '<button class="component-save" @click="$emit(\'save\', \'<template>new</template>\')">save</button>',
        },
        LiteratureEntryCard: {
          props: ['entry'],
          template: '<button class="literature-save" @click="$emit(\'updateCell\', \'title\', \'新版文献\')">save</button>',
        },
        EditorPane: { template: '<section class="editor-pane-content" />' },
        PixelLoader: true,
      },
    },
  })
}

describe('SearchResultSidebar', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()
    const settings = useSettingsStore()
    settings.profile.userId = 'u1'
    listLibraryTags.mockResolvedValue({ tags: [] })
    writeKnowledgeFile.mockResolvedValue({})
  })

  it('saves a library item and real content without rerunning search', async () => {
    const result: UnifiedSearchResult = {
      id: 'book-1', source: 'library', title: '图书', snippet: '', locator: 'book.md', updated_at: '', score: 1,
      matched_modes: ['title'], item: { item_id: 'book-1', title: '图书', display_title: '图书', source_path: 'book.md', item_type: 'book' },
    }
    const store = useWorkspaceStore()
    store.searchResults = response(result)
    const performSearch = vi.spyOn(store, 'performSearch')
    updateLibraryItem.mockResolvedValue({ item: { ...result.item, title: '新版图书', display_title: '新版图书' } })
    const wrapper = mountSidebar(result)
    await flushPromises()

    await wrapper.get('.library-save').trigger('click')
    await flushPromises()

    expect(writeKnowledgeFile).toHaveBeenCalledWith('u1', 'book.md', '新正文')
    expect(updateLibraryItem).toHaveBeenCalledOnce()
    expect(store.searchResults.results[0]?.title).toBe('新版图书')
    expect(performSearch).not.toHaveBeenCalled()
  })

  it('saves component source through the component API without rerunning search', async () => {
    const result: UnifiedSearchResult = {
      id: 'cards/a.vue', source: 'components', title: 'A', snippet: '', locator: 'cards/a.vue', updated_at: '', score: 1,
      matched_modes: ['title'], item: { component_id: 'cards/a.vue', title: 'A', tag: 'cards', source: '<template>old</template>', source_format: 'vue' },
    }
    const store = useWorkspaceStore()
    store.searchResults = response(result)
    const performSearch = vi.spyOn(store, 'performSearch')
    updateComponentLibraryItem.mockResolvedValue({ component: { ...result.item, source: '<template>new</template>' } })
    const wrapper = mountSidebar(result)

    await wrapper.get('.component-save').trigger('click')
    await flushPromises()

    expect(updateComponentLibraryItem).toHaveBeenCalledWith('u1', 'cards/a.vue', { source: '<template>new</template>' })
    expect(store.searchResults.results[0]?.item.source).toBe('<template>new</template>')
    expect(performSearch).not.toHaveBeenCalled()
  })

  it('loads and edits the exact literature row without rerunning search', async () => {
    const result: UnifiedSearchResult = {
      id: 'form-1:row-1', source: 'literature', title: '文献', snippet: '', locator: 'paper.pdf', updated_at: '', score: 1,
      matched_modes: ['title'], item: { form_id: 'form-1', row_id: 'row-1', title: '文献', file_name: 'paper.pdf', asset_path: 'paper.pdf' },
    }
    const form = { columns: [{ id: 'title', title: '标题', type: 'text', editable: true }], rows: [{ id: 'row-1', cells: { title: { value: '文献' } } }] }
    getSmartFormDb.mockResolvedValue({ form_id: 'form-1', user_id: 'u1', asset_dir: '', form, updated_at: '' })
    patchLiteratureRow.mockResolvedValue({ form: { ...form, rows: [{ id: 'row-1', cells: { title: { value: '新版文献' } } }] } })
    const store = useWorkspaceStore()
    store.searchResults = response(result)
    const performSearch = vi.spyOn(store, 'performSearch')
    const wrapper = mountSidebar(result)
    await flushPromises()

    await wrapper.get('.literature-save').trigger('click')
    await flushPromises()

    expect(patchLiteratureRow).toHaveBeenCalledWith('u1', 'form-1', 'row-1', { title: { value: '新版文献', status: 'ready' } })
    expect(store.searchResults.results[0]?.title).toBe('新版文献')
    expect(performSearch).not.toHaveBeenCalled()
  })

  it('switches literature sidebar between editable fields and the reused content editor', async () => {
    const result: UnifiedSearchResult = {
      id: 'form-1:row-1', source: 'literature', title: '文献', snippet: '', locator: 'paper.pdf', updated_at: '', score: 1,
      matched_modes: ['title'], item: { form_id: 'form-1', row_id: 'row-1', title: '文献', file_name: 'paper.pdf', asset_path: 'paper.pdf' },
    }
    getSmartFormDb.mockResolvedValue({ form_id: 'form-1', user_id: 'u1', asset_dir: '', form: { columns: [], rows: [] }, updated_at: '' })
    const wrapper = mountSidebar(result)
    await flushPromises()

    expect(wrapper.find('.sidebar-literature-editor').exists()).toBe(true)
    await wrapper.get('button[aria-label="查看文献内容"]').trigger('click')

    expect(wrapper.find('.editor-pane-content').exists()).toBe(true)
    expect(wrapper.find('.sidebar-literature-editor').exists()).toBe(false)
  })

  it('uses the shared editor sidebar close control', async () => {
    const result: UnifiedSearchResult = { id: 'book-1', source: 'library', title: '图书', snippet: '', locator: '', updated_at: '', score: 1, matched_modes: ['title'], item: { item_id: 'book-1' } }
    const wrapper = mountSidebar(result)
    await wrapper.get('.close-sidebar').trigger('click')
    expect(wrapper.emitted('close')).toHaveLength(1)
  })
})
