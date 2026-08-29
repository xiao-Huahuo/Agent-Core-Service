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
import searchPageSource from '@/views/SearchPage.vue?raw'

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

  it('reuses the same workspace editor sidebar as smart-form file cells', () => {
    expect(searchPageSource).toContain('await workspaceStore.openEditorSidebar(node)')
    expect(searchPageSource).not.toContain('SearchResultPreview')
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
    const openEditorSidebar = vi.spyOn(workspaceStore, 'openEditorSidebar').mockResolvedValue(undefined)
    vi.spyOn(workspaceStore, 'performSearch').mockResolvedValue(undefined)
    const wrapper = mount(SearchPage, {
      global: {
        stubs: {
          SplitText: true,
        },
      },
    })
    await wrapper.get('.search-box-submit').trigger('click')
    expect(wrapper.find('.results-empty').exists()).toBe(false)
    const result = wrapper.get('.result-card')

    await result.trigger('click')

    expect(workspaceStore.mainView).toBe('search')
    expect(openEditorSidebar).toHaveBeenCalledWith({ name: 'notes.md', path: 'docs/notes.md', isDir: false })
    expect(selectFile).not.toHaveBeenCalled()

    await result.trigger('dblclick')

    expect(workspaceStore.mainView).toBe('editor')
    expect(selectFile).toHaveBeenCalledOnce()
  })

  it('paginates the displayed result sequence at twenty items per page', async () => {
    const workspaceStore = useWorkspaceStore()
    workspaceStore.mainView = 'search'
    workspaceStore.searchUnified = false
    workspaceStore.searchQuery = 'note'
    workspaceStore.searchResults = {
      filename_results: Array.from({ length: 25 }, (_, index) => ({
        path: `docs/note-${index + 1}.md`,
        name: `note-${index + 1}.md`,
      })),
      fulltext_results: [],
      semantic_results: [],
    }
    vi.spyOn(workspaceStore, 'performSearch').mockResolvedValue(undefined)
    const wrapper = mount(SearchPage, {
      global: {
        stubs: {
          SplitText: true,
        },
      },
    })

    await wrapper.get('.search-box-submit').trigger('click')

    expect(wrapper.findAll('.result-card')).toHaveLength(20)
    expect(wrapper.find('.results-empty').exists()).toBe(false)
    expect(wrapper.get('.pagination-status').text()).toContain('1 / 2')

    await wrapper.get('.pagination-next').trigger('click')

    expect(wrapper.findAll('.result-card')).toHaveLength(5)
    expect(wrapper.get('.pagination-status').text()).toContain('2 / 2')
  })

  it('reuses the toolbar search dropdown for both initial and searched page states', async () => {
    const workspaceStore = useWorkspaceStore()
    workspaceStore.mainView = 'search'
    workspaceStore.addSearchHistory('previous query')
    vi.spyOn(workspaceStore, 'performSearch').mockResolvedValue(undefined)
    const wrapper = mount(SearchPage, {
      attachTo: document.body,
      global: { stubs: { SplitText: true } },
    })
    const pageInput = wrapper.get('.page-variant .search-input')

    await pageInput.trigger('focus')
    expect(document.body.querySelector('.page-search-dropdown')?.textContent).toContain('previous query')

    workspaceStore.searchQuery = 'alpha'
    workspaceStore.searchResults = {
      filename_results: [{ path: 'docs/notes.md', name: 'notes.md' }],
      fulltext_results: [],
      semantic_results: [],
    }
    await flushPromises()

    expect(document.body.querySelector('.page-search-dropdown')?.textContent).toContain('notes.md')

    wrapper.unmount()
  })

  it('does not focus the large search input merely because the search page opened', () => {
    const workspaceStore = useWorkspaceStore()
    workspaceStore.mainView = 'search'
    const wrapper = mount(SearchPage, {
      attachTo: document.body,
      global: { stubs: { SplitText: true } },
    })
    const input = wrapper.get('.page-variant .search-input')

    expect(document.activeElement).not.toBe(input.element)

    wrapper.unmount()
  })

  it('routes PDF results through the shared editor sidebar pipeline', async () => {
    const workspaceStore = useWorkspaceStore()
    workspaceStore.mainView = 'search'
    workspaceStore.searchQuery = 'report'
    workspaceStore.searchResults = {
      filename_results: [{ path: 'docs/report.pdf', name: 'report.pdf' }],
      fulltext_results: [],
      semantic_results: [],
    }
    workspaceStore.tree = [{
      name: 'docs',
      path: 'docs',
      isDir: true,
      children: [{ name: 'report.pdf', path: 'docs/report.pdf', isDir: false }],
    }]
    const openEditorSidebar = vi.spyOn(workspaceStore, 'openEditorSidebar').mockResolvedValue(undefined)
    vi.spyOn(workspaceStore, 'performSearch').mockResolvedValue(undefined)
    const wrapper = mount(SearchPage, {
      global: { stubs: { SplitText: true } },
    })

    await wrapper.get('.search-box-submit').trigger('click')
    await wrapper.get('.result-card').trigger('click')

    expect(openEditorSidebar).toHaveBeenCalledWith({
      name: 'report.pdf',
      path: 'docs/report.pdf',
      isDir: false,
    })
  })
})
