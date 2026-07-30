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

import { previewKnowledgeFile } from '@/api/knowledge'
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
    expect(wrapper.find('.results-empty').exists()).toBe(false)
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

  it('shows the shared editor mode bar while keeping Edit readonly', async () => {
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

    const modeButtons = wrapper.findAll('.search-result-preview .editor-mode-switch button')
    expect(modeButtons.map((button) => button.text())).toEqual(['Edit', 'Preview', 'Split'])
    expect(wrapper.get('.search-result-preview textarea').attributes('readonly')).toBeDefined()

    await modeButtons[1]?.trigger('click')

    expect(wrapper.find('.search-result-preview textarea').exists()).toBe(false)
    expect(wrapper.find('.search-result-preview .markdown-preview').exists()).toBe(true)
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

  it('clears the selected result when the active card is clicked again', async () => {
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
    vi.spyOn(workspaceStore, 'performSearch').mockResolvedValue(undefined)
    const wrapper = mount(SearchPage, {
      global: { stubs: { SplitText: true } },
    })
    await wrapper.get('.search-box-submit').trigger('click')
    const result = wrapper.get('.result-card')

    await result.trigger('click')
    expect(result.classes()).toContain('selected')
    expect(wrapper.find('.search-result-preview').exists()).toBe(true)

    await result.trigger('click')
    expect(result.classes()).not.toContain('selected')
    expect(wrapper.find('.search-result-preview').exists()).toBe(false)
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

  it('uses the native PDF viewer in Preview mode while keeping extracted text in Edit', async () => {
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
    vi.mocked(previewKnowledgeFile).mockResolvedValue({
      path: 'docs/report.pdf',
      kind: 'pdf',
      raw_url: '/knowledge/raw/report.pdf',
      content: 'extracted report text',
      mtime: '2026-07-31T09:00:00',
      size: 100,
      extension: '.pdf',
      readonly: true,
    })
    vi.spyOn(workspaceStore, 'performSearch').mockResolvedValue(undefined)
    const wrapper = mount(SearchPage, {
      global: { stubs: { SplitText: true } },
    })

    await wrapper.get('.search-box-submit').trigger('click')
    await wrapper.get('.result-card').trigger('click')
    await flushPromises()

    expect(wrapper.find('.search-result-preview textarea').exists()).toBe(true)
    await wrapper.findAll('.search-result-preview .editor-mode-switch button')[1]?.trigger('click')

    expect(wrapper.find('.search-result-preview .pdf-preview').exists()).toBe(true)
    expect(wrapper.find('.search-result-preview .code-preview').exists()).toBe(false)
  })
})
