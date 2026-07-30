/*
 * Search page result interaction tests.
 *
 * Usage:
 * Verifies that one click opens an in-page readonly preview while a double
 * click alone enters the regular editor workflow.
 */
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

import { useWorkspaceStore } from '@/stores/workspace'
import SearchPage from '@/views/SearchPage.vue'

vi.mock('@/api/agent', () => ({
  updateCurrentDocumentContext: vi.fn().mockResolvedValue(undefined),
}))

vi.mock('@/api/settings', () => ({
  rebuildKnowledgeRootStream: vi.fn(),
}))

vi.mock('@/api/knowledge', () => ({
  buildKnowledgeEventsUrl: vi.fn(() => '/events'),
  copyKnowledgePath: vi.fn(),
  createKnowledgeFile: vi.fn(),
  createKnowledgeFolder: vi.fn(),
  deleteKnowledgePath: vi.fn(),
  deleteKnowledgeTrashEntry: vi.fn(),
  getKnowledgeGraphStatus: vi.fn(),
  ingestKnowledgeFileStream: vi.fn(),
  ingestKnowledgePathStream: vi.fn(),
  listKnowledgeFiles: vi.fn(),
  listKnowledgeTrash: vi.fn(),
  previewKnowledgeFile: vi.fn(),
  readKnowledgeFile: vi.fn().mockResolvedValue({
    path: 'docs/notes.md',
    content: 'alpha beta',
    mtime: '2026-07-30T09:00:00',
    size: 10,
  }),
  rebuildKnowledgeGraph: vi.fn(),
  renameKnowledgePath: vi.fn(),
  restoreKnowledgeTrashEntry: vi.fn(),
  searchKnowledge: vi.fn(),
  uploadKnowledgeFile: vi.fn(),
  writeKnowledgeFile: vi.fn(),
}))

describe('SearchPage result opening', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('keeps single-click preview on the search page and opens the editor on double click', async () => {
    const workspaceStore = useWorkspaceStore()
    workspaceStore.mainView = 'search'
    workspaceStore.searchQuery = 'alpha'
    workspaceStore.searchResults = {
      filename_results: [{ path: 'docs/notes.md', name: 'notes.md' }],
      fulltext_results: [],
      semantic_results: [],
    }
    workspaceStore.tree = [{
      name: 'docs',
      path: 'docs',
      isDir: true,
      children: [{ name: 'notes.md', path: 'docs/notes.md', isDir: false }],
    }]
    const selectFile = vi.spyOn(workspaceStore, 'selectFile').mockResolvedValue(undefined)
    vi.spyOn(workspaceStore, 'performSearch').mockResolvedValue(undefined)
    const wrapper = mount(SearchPage, {
      global: {
        stubs: {
          SplitText: true,
        },
      },
    })
    await wrapper.get('.search-box-submit').trigger('click')
    const result = wrapper.get('.result-card')

    await result.trigger('click')

    expect(workspaceStore.mainView).toBe('search')
    expect(wrapper.find('.search-result-preview').exists()).toBe(true)
    expect(selectFile).not.toHaveBeenCalled()

    await result.trigger('dblclick')

    expect(workspaceStore.mainView).toBe('editor')
    expect(selectFile).toHaveBeenCalledOnce()
  })

  it('does not pass lexical highlighting into a semantic-only result preview', async () => {
    const workspaceStore = useWorkspaceStore()
    workspaceStore.mainView = 'search'
    workspaceStore.searchQuery = 'concept'
    workspaceStore.searchResults = {
      filename_results: [],
      fulltext_results: [],
      semantic_results: [{
        memory_id: 'memory_1',
        source_uri: 'docs/notes.md',
        content: 'alpha beta',
      }],
    }
    workspaceStore.tree = [{
      name: 'docs',
      path: 'docs',
      isDir: true,
      children: [{ name: 'notes.md', path: 'docs/notes.md', isDir: false }],
    }]
    vi.spyOn(workspaceStore, 'performSearch').mockResolvedValue(undefined)
    const wrapper = mount(SearchPage, {
      global: {
        stubs: {
          SplitText: true,
        },
      },
    })

    await wrapper.get('.search-box-submit').trigger('click')
    await wrapper.get('.result-card').trigger('click')
    await flushPromises()

    expect(wrapper.get('.search-result-preview textarea').attributes('readonly')).toBeDefined()
    expect(wrapper.find('.search-result-preview .highlight-layer').exists()).toBe(false)
  })
})
